import csv
import os
import argparse
import configparser
from datetime import datetime

from piecash import open_book
from piecash.core import Transaction

from transaction_manager import TransactionManager
from commodity_manager import CommodityManager


def generate_monthly_report(gnucash_file: str):
    # Read the configuration file
    config = read_config_file(gnucash_file)

    if not config['gnucash_filename']:
        raise ValueError('No input book provided - provide one using the --file argument or' +
                         'through config.ini')

    # Define datastructures used to read files
    with open_book(config['gnucash_filename']) as book:
        # Find the earliest transaction date
        start_date = book.get(Transaction).order_by(Transaction.post_date).first().post_date
        print(f'Earliest recorded transaction is on {start_date}')

        # Get a set of all transaction ids - make sure we are handling all of them
        unprocessed_transactions = {t for t in book.get(Transaction)}
        print(f'Found {len(unprocessed_transactions)} transactions to process')

        print(f'Processing income and expense accounts...')
        income_manager = TransactionManager(start_date, book, 'INCOME', 'Income')
        unprocessed_transactions -= income_manager.transactions_handled
        expense_manager = TransactionManager(start_date, book, 'EXPENSE', 'Expenses')
        unprocessed_transactions -= expense_manager.transactions_handled

        # Remove credit card payments from unprocessed - we care about the expenses, not the payments
        unprocessed_transactions = {t for t in unprocessed_transactions if sorted([s.account.type for s in t.splits]) != ['BANK', 'CREDIT']}

        # Record transfers into savings accounts
        print(f'Processing transfers...')
        savings_manager = TransactionManager(start_date, book, None, 'Savings', managed_root='Assets:Current Assets:Savings Account', ignore_categories=['INCOME', 'EXPENSE'])
        unprocessed_transactions -= savings_manager.transactions_handled
        investment_manager = TransactionManager(start_date, book, None, 'Investment Contributions', managed_root='Assets:Investments', ignore_categories=['INCOME', 'EXPENSE'])
        unprocessed_transactions -= investment_manager.transactions_handled

        # This isn't expected to be zero - some transactions are shuffling money around (like moving to ATB Unlimited prior to investment buy)
        print(f'  Complete - {len(unprocessed_transactions)} transactions remaining')

        # Used for total asset values
        print(f'Processing total assets...')
        asset_manager = TransactionManager(start_date, book, None, 'Assets', managed_root='Assets')
        unprocessed_transactions -= asset_manager.transactions_handled
        liabilities_manager = TransactionManager(start_date, book, 'LIABILITY', 'Liabilities')
        unprocessed_transactions -= liabilities_manager.transactions_handled

        # Commodities with fluctuating prices
        commodities_manager = CommodityManager(start_date, book, None, 'Present Values', managed_root='Assets:Investments')
        unprocessed_transactions -= commodities_manager.transactions_handled
    
        # Generate report csv
        csv_filename = os.path.join(config['output_folder'], 
                                    datetime.now().strftime('Summary-%Y-%m-%d.csv'))
        create_csv_report(csv_filename, start_date, income_manager, expense_manager, 
                        savings_manager, investment_manager, asset_manager, 
                        liabilities_manager, commodities_manager, config)
        print(f'Report saved as {csv_filename}')


def create_csv_report(csv_filename: str, 
                      start_date: datetime.date,
                      income_manager: TransactionManager, 
                      expense_manager: TransactionManager,
                      savings_manager: TransactionManager,
                      investment_manager: TransactionManager,
                      asset_manager: TransactionManager,
                      liabilities_manager: TransactionManager,
                      commodities_manager: CommodityManager,
                      config: dict):
    # Determine field names
    fieldnames = ['Month']
    fieldnames.extend(income_manager.get_header_names(config['separate_income_columns']))
    fieldnames.extend(expense_manager.get_header_names(config['separate_expense_columns']))
    fieldnames.extend(savings_manager.get_header_names(None))
    fieldnames.extend(investment_manager.get_header_names(None))
    fieldnames.extend(asset_manager.get_header_names(config['separate_asset_columns']))
    fieldnames.extend(liabilities_manager.get_header_names(None))
    fieldnames.extend(commodities_manager.get_header_names(None))

    # Collect all data into a list of rows indexed by month
    rows = {}

    income_columns = income_manager.get_report_data(start_date, fieldnames, config['separate_income_columns'])
    for month, income in income_columns.items():
        # Income is recorded as a negative - use abs to reverse that
        rows[month] = {k:abs(v) for k,v in income.items()}

    expense_columns = expense_manager.get_report_data(start_date, fieldnames, config['separate_expense_columns'])
    for month, expenses in expense_columns.items():
        rows[month].update(expenses)

    savings_columns = savings_manager.get_report_data(start_date, fieldnames, None)
    for month, saving in savings_columns.items():
        rows[month].update(saving)

    investment_columns = investment_manager.get_report_data(start_date, fieldnames, None)
    for month, investment in investment_columns.items():
        rows[month].update(investment)

    asset_columns = asset_manager.get_report_data(start_date, fieldnames, config['separate_asset_columns'], sum_values=True)
    for month, asset in asset_columns.items():
        rows[month].update(asset)

    liability_columns = liabilities_manager.get_report_data(start_date, fieldnames, None, sum_values=True)
    for month, liability in liability_columns.items():
        rows[month].update(liability)

    commodity_columns = commodities_manager.get_report_data(start_date, fieldnames, None, sum_values=True)
    for month, commodity in commodity_columns.items():
        rows[month].update(commodity)

    with open(csv_filename, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for month, row in rows.items():
            # Skip if all values are 0, sometimes true for the past month
            if all([v == 0 for v in row.values()]):
                continue

            row['Month'] = month
            writer.writerow(row)


def parse_accounts(account_config: str):
    """
    Given a string from the config file like A, B, [C, D], creates
    a list of lists grouping by square brackets.
    """
    result = []

    # Tracking position
    current_string = ""
    in_group = False

    for char in account_config:
        if char == ',' and in_group:
            result[-1].append(current_string.strip())
            current_string = ''
        elif char == ',' and not in_group:
            if current_string:
                result.append([current_string.strip()])
            current_string = ''
        elif char == '[':
            result.append([])  # Start the group
            in_group = True
        elif char == ']':
            result[-1].append(current_string.strip())
            current_string = ''
            in_group = False
        else:
            current_string += char
    
    # If there is a current string remaining, append it
    if current_string:
        result.append([current_string.strip()])

    return result

def read_config_file(gnucash_filename: str):
    """
    Returns a configuration dictionary either using default values or those taken from the 
    config.ini file in this folder.
    """
    # Setup defaults
    config_dictionary = {
        'gnucash_filename': gnucash_filename,
        'output_folder': os.path.dirname(__file__),
        'separate_income_columns': [],
        'separate_expense_columns': [],
        'main_account': 'Assets:Current Assets:Checking Account'
    }

    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    if not os.path.exists(config_path):
        print('No config.ini found, using defaults.')
        return config_dictionary
    
    config = configparser.ConfigParser()
    config.read(config_path)

    # Paths section
    paths = config['Paths']
    if 'default_gnucash_book' in paths:
        config_dictionary['gnucash_filename'] = paths['default_gnucash_book']
    if 'output_folder' in paths:
        config_dictionary['output_folder'] = paths['output_folder']
    
    # Income section
    income = config['Income']
    if 'separate_income' in income:
        config_dictionary['separate_income_columns'] = parse_accounts(income['separate_income'])

    # Expenses section
    expenses = config['Expenses']
    if 'separate_expenses' in expenses:
        config_dictionary['separate_expense_columns'] = parse_accounts(expenses['separate_expenses'])

    # Assets section
    assets = config['Assets']
    if 'separate_assets' in assets:
        config_dictionary['separate_asset_columns'] = parse_accounts(assets['separate_assets'])

    return config_dictionary
    

if __name__ == '__main__':
    # Parse arguments
    parser = argparse.ArgumentParser(description='Generate a report from a GNUCash file.')
    parser.add_argument('--file', required=False)
    args = parser.parse_args()

    generate_monthly_report(args.file)
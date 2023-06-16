# TODO
# Income will be very similar to expenses - create a generic manager and inherit from it with a few parameters
# Main sections that will get a manager: Income, Expenses, Savings, Investments

import csv
import os
import argparse
import configparser
from datetime import datetime

from piecash import open_book
from piecash.core import Transaction

from transaction_manager import TransactionManager


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

        income_manager = TransactionManager(start_date, book, 'INCOME', 'Income')
        expense_manager = TransactionManager(start_date, book, 'EXPENSE', 'Expenses')
    
    # Generate report csv
    csv_filename = os.path.join(config['output_folder'], 
                                datetime.now().strftime('Summary-%Y-%m-%d.csv'))
    create_csv_report(csv_filename, start_date, income_manager, expense_manager, config)
    print('Report creation finished.')


def create_csv_report(csv_filename: str, 
                      start_date: datetime.date,
                      income_manager: TransactionManager, 
                      expense_manager: TransactionManager, 
                      config: dict):
    # Determine field names
    fieldnames = ['Month']
    fieldnames.extend(income_manager.get_header_names(config['separate_income_columns']))
    fieldnames.extend(expense_manager.get_header_names(config['separate_expense_columns']))

    with open(csv_filename, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Collect all data into a list of rows indexed by month
        rows = {}

        income_columns = income_manager.get_report_data(start_date, config['separate_income_columns'])
        for month, income in income_columns.items():
            # Income is recorded as a negative - use abs to reverse that
            rows[month] = {k:abs(v) for k,v in income.items()}

        expense_columns = expense_manager.get_report_data(start_date, config['separate_expense_columns'])
        for month, expenses in expense_columns.items():
            rows[month].update(expenses)

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
        elif char == ',' and not in_group and current_string:
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
        'separate_expense_columns': []
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

    return config_dictionary
    

if __name__ == '__main__':
    # Parse arguments
    parser = argparse.ArgumentParser(description='Generate a report from a GNUCash file.')
    parser.add_argument('--file', required=False)
    args = parser.parse_args()

    generate_monthly_report(args.file)
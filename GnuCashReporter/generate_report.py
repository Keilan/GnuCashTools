# TODO
# Main sections that will get a manager: Income, Expenses, Savings, Investments
# Add config file that isn't stored in gitlab, this includes default GNUCash location

import argparse
import datetime

from piecash import open_book
from piecash.core import Transaction
from piecash.core.transaction import Split

from expense_manager import ExpenseManager


def generate_monthly_report(gnucash_file: str):
    # Define datastructures used to read files
    with open_book(gnucash_file) as book:
        # Find the earliest transaction date
        start_date = book.get(Transaction).order_by(Transaction.post_date).first().post_date
        print(f'Earliest recorded transaction is on {start_date}')

        expense_manager = ExpenseManager(start_date, book)


if __name__ == '__main__':
    # Parse arguments
    parser = argparse.ArgumentParser(description='Generate a report from a GNUCash file.')
    parser.add_argument('gnucash_file')
    args = parser.parse_args()

    generate_monthly_report(args.gnucash_file)
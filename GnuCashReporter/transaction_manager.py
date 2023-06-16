import datetime
import calendar
from decimal import Decimal

from piecash.core import Transaction
from piecash.core.transaction import Split

class TransactionDate:
    year: int
    month: int

    def __init__(self, year, month):
        self.year = year
        self.month = month

    def __eq__(self, other):
        return self.year == other.year and self.month == other.month
    
    def __hash__(self):
        """
        Because we redefined __eq__ we no longer have a default hash, use the
        tuple hash method.
        """
        return hash((self.year, self.month))

    def get_next(self):
        """
        Returns a new transaction date representing the next month.
        """
        next_date = TransactionDate(self.year, self.month+1)
        if next_date.month == 13:
            next_date = TransactionDate(self.year+1, 1)
        return next_date
    
    def in_future(self):
        today = datetime.date.today()
        if self.year > today.year:
            return True
        elif self.year == today.year and self.month > today.month:
            return True
        return False

    def __repr__(self):
        return f'{calendar.month_name[self.month]} {self.year}'


class Account:
    """
    A tree structure where accounts are summed up per month at each node and that
    sum is then added to all parent nodes.
    """
    name: str
    parent: 'Account'
    monthly_sums: dict[TransactionDate, list[Decimal]]

    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.monthly_sums = {}

    def __repr__(self):
        return f'Account: {self.name}'


class TransactionManager:
    """
    Handles reading in income/expense values and dealing with related calculations including summing the
    monthly totals for accounts at various levels in the account tree.
    """
    accounts: dict[str, Account]
    transaction_type: str
    account_label: str

    def __init__(self, start_date, book, transaction_type, account_label):  
        # Initialize variables
        self.accounts = {}
        self.transaction_type = transaction_type
        self.account_label = account_label

        # Iterate through the months, storing transactions
        current_date = TransactionDate(start_date.year, start_date.month)
        today = datetime.date.today()
        while(not current_date.in_future()):
            # Calculate the next date
            next_date = current_date.get_next()

            # Get all transactions for the month
            transactions = book.get(Transaction).filter(
                Transaction.post_date >= datetime.date(current_date.year, current_date.month, 1),
                Transaction.post_date < datetime.date(next_date.year, next_date.month, 1))
                   
            # Look through each split that is associated with an transaction
            for transaction in transactions:
                for split in self.find_managed_splits(transaction):
                    self.update_tree(split, current_date)

            # Update current_date
            current_date = next_date

    def update_tree(self, split: Split, month: TransactionDate):
        """
        Adds the given split to the tree, including creating new tree nodes
        as needed and updating totals.
        """
        account = split.account

        # If the account isn't in our tree, create it, using a stack to create
        # each node and link it to the correct parent
        if account.fullname not in self.accounts:
            account_stack = []

            # Add each transaction to the stack
            while account.type == self.transaction_type:
                
                if account.fullname in self.accounts:
                    current_account = self.accounts[account.fullname]
                else:
                    current_account = Account(account.fullname)
                    self.accounts[account.fullname] = current_account
                account_stack.append(current_account)
                account = account.parent
            
            # Move back through the stack assigning parents
            current = account_stack.pop()
            while account_stack:
                child = account_stack.pop()
                child.parent = current
                current = child
        
        # Add the amount, creating month indicators as necessary
        value = split.value
        current = self.accounts[split.account.fullname]
        while current is not None:
            if month not in current.monthly_sums:
                current.monthly_sums[month] = 0
            current.monthly_sums[month] += value
            current = current.parent

    def get_report_data(self, start_date: datetime.date, separate_columns: list):
        # Store the data in a dictionary mapping
        monthly_data = {}
        current_date = TransactionDate(start_date.year, start_date.month)
        while not current_date.in_future():

            # Store total value
            total = self.accounts[self.account_label].monthly_sums.get(current_date, 0)
            total_label = f'Total {self.account_label}'
            monthly_data[current_date] = {total_label: total}

            # Handle separate columns
            if separate_columns:
                other = total
                
                # Process each group
                for group in separate_columns:
                    group_name = ''
                    group_sum = 0

                    # Process each column, subtracting the sum from the total
                    for column in group:
                        # Update the name, if there are multiple entries in the group, combine them
                        if group_name:
                            group_name += '/'
                        group_name += column.split(':')[-1]

                        group_sum += self.accounts[column].monthly_sums.get(current_date, 0)
                        
                    other -= group_sum
                    monthly_data[current_date][group_name] = group_sum
                
                # Store other values
                other_label = f'Other {self.account_label}'
                monthly_data[current_date][other_label] = other
                
            current_date = current_date.get_next()
        
        return monthly_data

    # Helper Functions
    def get_header_names(self, separate_columns: list):
        headers = [f'Total {self.account_label}']

        if separate_columns:
            for group in separate_columns:
                group_name = ''
                for column in group:
                    # Update the name, if there are multiple entries in the group, combine them
                    if group_name:
                        group_name += '/'
                    group_name += column.split(':')[-1]
                headers.append(group_name)

            headers.append(f'Other {self.account_label}')
        
        return headers

    def find_managed_splits(self, transaction: Transaction):
        """
        Returns a list of splits that are associated with accounts.
        """
        splits = []
        for split in transaction.splits:
            if split.account.type == self.transaction_type:
                splits.append(split)
        return splits
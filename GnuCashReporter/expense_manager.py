import datetime
from collections import namedtuple
from decimal import Decimal

from piecash.core import Transaction
from piecash.core.transaction import Split


TransactionDate = namedtuple('TransactionDate', ['year', 'month'])

class ExpenseAccount:
    """
    A tree structure where expenses are summed up per month at each node and that
    sum is then added to all parent nodes.
    """
    name: str
    parent: 'ExpenseAccount'
    monthly_sums: dict[TransactionDate, list[Decimal]]

    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.monthly_sums = {}

    def __repr__(self):
        return f'ExpenseAccount: {self.name}'


class ExpenseManager:
    """
    Handles reading in expense values and dealing with related calculations including summing the
    monthly totals for expense accounts at various levels in the expense account tree.
    """
    expense_accounts: dict[str, ExpenseAccount]

    def __init__(self, start_date, book):  
        # Initialize variables
        self.expense_accounts = {}

        # Iterate through the months, storing expenses
        current_date = TransactionDate(start_date.year, start_date.month)
        today = datetime.date.today()
        while(current_date.year != today.year or current_date.month <= today.month):
            # Calculate the next date
            next_date = TransactionDate(current_date.year, current_date.month+1)
            if next_date.month == 13:
                next_date = TransactionDate(current_date.year+1, 1)

            # Get all transactions for the month
            transactions = book.get(Transaction).filter(
                Transaction.post_date >= datetime.date(current_date.year, current_date.month, 1),
                Transaction.post_date < datetime.date(next_date.year, next_date.month, 1))
                   
            # Look through each split that is associated with an expense
            for transaction in transactions:
                for split in self.find_expense_splits(transaction):
                    self.update_expense_tree(split, current_date)

            # Update current_date
            current_date = next_date

    def update_expense_tree(self, split: Split, month: TransactionDate):
        """
        Adds the given split to the tree, including creating new tree nodes
        as needed and updating totals.
        """
        account = split.account

        # If the account isn't in our tree, create it, using a stack to create
        # each node and link it to the correct parent
        if account.fullname not in self.expense_accounts:
            account_stack = []

            # Add each expense to the stack
            while account.type == 'EXPENSE':
                
                if account.fullname in self.expense_accounts:
                    current_expense_account = self.expense_accounts[account.fullname]
                else:
                    current_expense_account = ExpenseAccount(account.fullname)
                    self.expense_accounts[account.fullname] = current_expense_account
                account_stack.append(current_expense_account)
                account = account.parent
            
            # Move back through the stack assigning parents
            current = account_stack.pop()
            while account_stack:
                child = account_stack.pop()
                child.parent = current
                current = child
        
        # Add the amount, creating month indicators as necessary
        value = split.value
        current = self.expense_accounts[split.account.fullname]
        while current is not None:
            if month not in current.monthly_sums:
                current.monthly_sums[month] = 0
            current.monthly_sums[month] += value
            current = current.parent

    # Helper Functions
    def find_expense_splits(self, transaction: Transaction):
        """
        Returns a list of splits that are associated with expense accounts.
        """
        expense_splits = []
        for split in transaction.splits:
            if split.account.type == 'EXPENSE':
                expense_splits.append(split)
        return expense_splits


# book.get(Transaction).filter(Transaction.post_date>=datetime.date(2021, 5, 10)).all()
# book.get(Transaction).filter(Transaction.splits.any(Split.value > 25)).count()
import datetime
from collections import namedtuple

from piecash.core import Transaction


TransactionDate = namedtuple('TransactionDate', ['year', 'month'])

class ExpenseManager:
    def __init__(self, start_date, book):
        sum = 0
        
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
                Transaction.post_date < datetime.date(next_date.year, next_date.month, 1)).count()
            print(current_date, transactions)
            sum += transactions

            # Update current_date
            current_date = next_date
        
        print('Total', sum)



# book.get(Transaction).filter(Transaction.post_date>=datetime.date(2021, 5, 10)).all()
# book.get(Transaction).filter(Transaction.splits.any(Split.value > 25)).count()
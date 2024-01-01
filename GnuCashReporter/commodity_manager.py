import datetime
from decimal import Decimal

from transaction_manager import Account, TransactionDate, TransactionManager

from piecash.core import Price, Commodity, Split

    
class CommodityAccount(Account):
    monthly_sums: dict[TransactionDate, list[list[Decimal]]]


class CommodityManager(TransactionManager):
    """
    This will be a subclass of the Transaction manager that tracks shares of
    commodities and generates the report with pricing at a given time.
    """
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
            while self.is_managed_account(account):
                
                if account.fullname in self.accounts:
                    current_account = self.accounts[account.fullname]
                else:
                    current_account = CommodityAccount(account.fullname)
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
        commodity = split.account.commodity
        quantity = split.quantity
        current = self.accounts[split.account.fullname]
        while current is not None:
            if month not in current.monthly_sums:
                current.monthly_sums[month] = {}
            if commodity not in current.monthly_sums[month]:
                current.monthly_sums[month][commodity] = 0
            current.monthly_sums[month][commodity] += quantity
            current = current.parent

    def print_tree(self, date: TransactionDate = None):
        keys = sorted(self.accounts.keys())
        for key in keys:
            indent = "    " * key.count(':')
            label = key[key.rindex(':')+1:] if ':' in key else key

            if date:
                total = self.accounts[key].monthly_sums.get(date, {})
            else:
                # Sum the values using the commodity list function
                commodity_sum = {}
                for value in self.accounts[key].monthly_sums.values():
                    commodity_sum = self.add_commodity_dicts(commodity_sum, value)

                total = commodity_sum

            total_string = ', '.join([f'{k.mnemonic} - {total[k]:.2f}' for k in sorted(total.keys(), key=lambda c: c.mnemonic)])
            print(f'{indent}{label}: {total_string}')

    def get_report_data(self, start_date: datetime.date, headers: list[str], separate_columns: list, sum_values: bool = False):
        """
        Tracks the quantity of securities and only converts values to CAD at the end.
        """
        # Store the data in a dictionary mapping
        monthly_data = {}
        current_date = TransactionDate(start_date.year, start_date.month)
        root_account = self.get_tree_root()
        other_label = None

        while not current_date.in_future():

            # Store total value
            total = self.accounts[root_account].monthly_sums.get(current_date, {})
            total_label = f'Total {self.account_label}' if separate_columns else self.account_label
            monthly_data[current_date] = {total_label: total}

            if sum_values and current_date.get_previous() in monthly_data:
                summed_value = self.add_commodity_dicts(monthly_data[current_date][total_label], monthly_data[current_date.get_previous()][total_label])
                monthly_data[current_date][total_label] = summed_value

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

                    if sum_values and current_date.get_previous() in monthly_data:
                        summed_value = self.add_commodity_dicts(monthly_data[current_date][group_name], monthly_data[current_date.get_previous()][group_name])
                        monthly_data[current_date][group_name] = summed_value
                
                # Store other values
                other_label = f'Other {self.account_label}'
                monthly_data[current_date][other_label] = other

                if sum_values and current_date.get_previous() in monthly_data:
                    summed_value = self.add_commodity_dicts(monthly_data[current_date][other_label], monthly_data[current_date.get_previous()][other_label])
                    monthly_data[current_date][other_label] = summed_value
                
            current_date = current_date.get_next()
        
        # If the other category is always zero, remove it (this means other headers use up all the values)
        if other_label and all([len(m[other_label]) == 0 for m in monthly_data.values()]):
            for values in monthly_data.values():
                del values[other_label]
            headers.remove(other_label)

        # Convert to base currency
        for date in monthly_data:
            for label in monthly_data[date]:
                total = 0
                for commodity in monthly_data[date][label]:
                    quantity = monthly_data[date][label][commodity]
                    total += self.to_base_currency(quantity, commodity, date)
                monthly_data[date][label] = total

        return monthly_data
    
    def add_commodity_dicts(self, d1: dict[Commodity], d2: dict[Commodity]) -> dict[Commodity]:
        """
        Given two dicts of commodities - adds them together, creating new values if needed.
        """
        keys = set(d1.keys()) | set(d2.keys())
        return {k: d1.get(k, 0) + d2.get(k, 0) for k in keys}
    
    def to_base_currency(self, quantity: Decimal, commodity: Commodity, date: TransactionDate) -> Decimal:
        if commodity == self.base_currency:
            return quantity

        # Find the latest price before the last day of the transaction month (subtract 1 day from the next month to get the last day)
        price_date = datetime.date(date.get_next().year, date.get_next().month, 1)
        price_date -= datetime.timedelta(days=1)

        latest_price = commodity.prices.filter_by(currency=self.base_currency).filter(Price.date <= price_date).order_by(Price.date.desc()).first()

        # If no price exists, just use the earliest available
        if latest_price is None:
            latest_price = commodity.prices.filter_by(currency=self.base_currency).order_by(Price.date.asc()).first()

        assert latest_price is not None

        return quantity * latest_price.value
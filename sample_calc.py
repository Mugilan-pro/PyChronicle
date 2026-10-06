"""Sample calculation script for PyChronicle time-travel debugging demonstration."""

balance = 100
transactions = [25, -10, 50, -15, 30]

for amount in transactions:
    if amount > 0:
        category = "deposit"
    else:
        category = "withdrawal"
    balance += amount

print(f"Final Balance: ${balance}")

def calculate_total(numbers: list[int]) -> int:
    total = 0
    for number in numbers:
        total += number
    return total


prices = [12, 8, 15]
tax_rate = 0.1
subtotal = calculate_total(prices)
grand_total = subtotal * (1 + tax_rate)
print(f"Subtotal: {subtotal}; total with tax: {grand_total:.2f}")
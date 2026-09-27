"""Sample algorithm target script for PyChronicle time-travel debugging.

Calculates Fibonacci numbers and cumulative running statistics.
"""

def compute_fibonacci_stats(limit: int = 6):
    total_sum = 0
    fib_sequence = []
    a, b = 0, 1

    for step in range(limit):
        fib_sequence.append(a)
        total_sum += a
        next_val = a + b
        a = b
        b = next_val

    is_even_total = (total_sum % 2 == 0)
    summary = {
        "count": limit,
        "sequence": fib_sequence,
        "sum": total_sum,
        "is_even": is_even_total,
    }
    return summary


if __name__ == "__main__":
    result = compute_fibonacci_stats()
    print("Done:", result)

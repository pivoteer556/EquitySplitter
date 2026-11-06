from decimal import Decimal


def calculate_equity_deltas(amount_due: Decimal, amount_paid: Decimal, bonus_rate: Decimal = Decimal("0.50")) -> tuple[Decimal, Decimal]:
    if amount_due < 0 or amount_paid < 0:
        raise ValueError("Amounts cannot be negative")

    base = min(amount_paid, amount_due)
    overpayment = max(amount_paid - amount_due, Decimal("0"))
    bonus = overpayment * bonus_rate
    return base, bonus


def next_running_balance(current_balance: Decimal, base_delta: Decimal, bonus_delta: Decimal) -> Decimal:
    return current_balance + base_delta + bonus_delta
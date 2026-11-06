from decimal import Decimal

import pytest

from app.services.equity import calculate_equity_deltas, next_running_balance


def test_calculate_equity_deltas_with_overpayment():
    base, bonus = calculate_equity_deltas(Decimal("1000"), Decimal("1200"))
    assert base == Decimal("1000")
    assert bonus == Decimal("100.00")


def test_calculate_equity_deltas_without_overpayment():
    base, bonus = calculate_equity_deltas(Decimal("1000"), Decimal("900"))
    assert base == Decimal("900")
    assert bonus == Decimal("0.00")


def test_calculate_equity_deltas_negative_amount_raises():
    with pytest.raises(ValueError):
        calculate_equity_deltas(Decimal("-1"), Decimal("100"))


def test_next_running_balance():
    new_balance = next_running_balance(Decimal("1500"), Decimal("400"), Decimal("50"))
    assert new_balance == Decimal("1950")
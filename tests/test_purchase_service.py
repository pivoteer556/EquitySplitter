from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models import PropertyPurchase
from app.services.purchase import PurchaseStage, owner_shares, purchase_stage

T = datetime(2026, 1, 1, tzinfo=UTC)


def _p(**kw):
    return PropertyPurchase(purchasePrice=Decimal("1"), **kw)


@pytest.mark.parametrize(
    ("purchase", "stage"),
    [
        (None, "listed"),
        (_p(), "listed"),
        (_p(applicationFiledAt=T), "application_filed"),
        (_p(applicationFiledAt=T, intentToProceedAt=T), "intent_to_proceed"),
        (_p(applicationFiledAt=T, intentToProceedAt=T, closedAt=T), "closed"),
    ],
    ids=["none", "no application", "application", "itp", "closed"],
)
def test_purchase_stage(purchase, stage):
    assert purchase_stage(purchase) == stage


def test_stage_values_are_the_four_names():
    assert [s.value for s in PurchaseStage] == ["listed", "application_filed", "intent_to_proceed", "closed"]


def test_shares_example_sum_exactly_to_the_monthly_payment():
    shares = owner_shares([Decimal("80000"), Decimal("50000"), Decimal("30000")], Decimal("2001.08"))
    assert shares is not None
    assert [s.percent for s in shares] == [Decimal("50"), Decimal("31.25"), Decimal("18.75")]
    assert [s.monthly for s in shares] == [Decimal("1000.54"), Decimal("625.34"), Decimal("375.20")]
    assert sum(s.monthly for s in shares) == Decimal("2001.08")


def test_rounding_remainder_goes_to_the_largest_owner():
    shares = owner_shares([Decimal("1"), Decimal("1"), Decimal("1")], Decimal("100.00"))
    assert shares is not None
    assert sum(s.monthly for s in shares) == Decimal("100.00")
    assert [s.monthly for s in shares] == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]


def test_single_owner_takes_everything():
    shares = owner_shares([Decimal("5000")], Decimal("1800.00"))
    assert shares is not None
    assert [(s.percent, s.monthly) for s in shares] == [(Decimal("100"), Decimal("1800.00"))]


@pytest.mark.parametrize(
    "downs",
    [[], [None], [Decimal("0")], [Decimal("100"), None], [None, None], [Decimal("0"), Decimal("0")]],
)
def test_no_split_when_down_payments_are_unset_or_zero(downs):
    assert owner_shares(downs, Decimal("1800.00")) is None

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import NamedTuple

from app.models.property_purchase import PropertyPurchase

CENT = Decimal("0.01")


class PurchaseStage(StrEnum):
    """The four purchase stages, in order. The one definition of the names."""

    LISTED = "listed"
    APPLICATION_FILED = "application_filed"
    INTENT_TO_PROCEED = "intent_to_proceed"
    CLOSED = "closed"


def purchase_stage(purchase: PropertyPurchase | None) -> PurchaseStage:
    """The stage is derived, never stored: the latest stage whose timestamp is set wins. (The CHECK constraints
    guarantee a later timestamp is never set without the earlier ones.)"""
    if purchase is None:
        return PurchaseStage.LISTED
    if purchase.closedAt is not None:
        return PurchaseStage.CLOSED
    if purchase.intentToProceedAt is not None:
        return PurchaseStage.INTENT_TO_PROCEED
    if purchase.applicationFiledAt is not None:
        return PurchaseStage.APPLICATION_FILED
    return PurchaseStage.LISTED


class OwnerShare(NamedTuple):
    percent: Decimal  # share of total down payments, to two places
    monthly: Decimal  # estimated share of the monthly payment, to cents


def owner_shares(downPayments: Sequence[Decimal | None], monthlyPayment: Decimal) -> list[OwnerShare] | None:
    """Each owner's share of the total down payments and of the monthly payment, in the order given. Shares are
    rounded to cents and the rounding remainder goes to the largest owner (first of equals), so they sum EXACTLY to
    monthlyPayment. Returns None, not a split, when any down payment is unset or the total is not positive: the
    caller shows "not set" rather than guessing or dividing by zero."""
    if not downPayments or any(d is None for d in downPayments):
        return None
    amounts = [d for d in downPayments if d is not None]
    total = sum(amounts, Decimal(0))
    if total <= 0:
        return None
    monthly = [(monthlyPayment * d / total).quantize(CENT, ROUND_HALF_UP) for d in amounts]
    monthly[amounts.index(max(amounts))] += monthlyPayment - sum(monthly, Decimal(0))
    percents = [(d * 100 / total).quantize(CENT, ROUND_HALF_UP) for d in amounts]
    return [OwnerShare(p, m) for p, m in zip(percents, monthly, strict=True)]

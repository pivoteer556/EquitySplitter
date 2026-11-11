"""GET /properties/{id} returns the purchase terms and stage (and a listing summary); GET /properties/{id}/owners
returns each owner's down payment, share of the down payments and estimated monthly share. All additive: the old keys
are unchanged. Stage comes only from purchase_stage() and shares only from owner_shares() (their own tests are in
tests/test_purchase_service.py); these tests check the wiring and the JSON shape. Rows are seeded through
session_factory so no call rotates a token before the one under test."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.models import (
    Loan,
    Property,
    PropertyAgreement,
    PropertyListing,
    PropertyPurchase,
    User,
    UserProperty,
)
from app.services.auth import unusable_password_hash
from tests.conftest import bearer
from tests.test_connection_requests import _buyer
from tests.test_property_list import _second_officer

URL = "/api/v1/properties"
AGREEMENT = {"noticeDays": 30, "valuationMethod": "appraisal", "partialClaimMethod": "pro_rata"}
T1 = datetime(2026, 10, 20, tzinfo=UTC)
T2 = datetime(2026, 11, 5, tzinfo=UTC)
T3 = datetime(2026, 12, 18, tzinfo=UTC)


def _seed(session_factory, institution_id, *, loan=True, listing=False):
    db = session_factory()
    try:
        prop = Property(
            institutionId=institution_id,
            address="418 Larkspur Court",
            loanAmount=325000,
            currentBalance=325000,
            monthlyPayment=Decimal("2001.08"),
            status="pending_acknowledgement",
        )
        if loan:
            prop.loan = Loan(
                loanAmount=325000,
                currentBalance=325000,
                monthlyPayment=Decimal("2001.08"),
                interestRatePercent=Decimal("6.250"),
                termMonths=360,
            )
        db.add(prop)
        db.flush()
        db.add(PropertyAgreement(propertyId=prop.id, **AGREEMENT))
        if listing:
            db.add(
                PropertyListing(
                    propertyId=prop.id,
                    status="listed",
                    askingPrice=Decimal("489000.00"),
                    bedrooms=4,
                    bathrooms=Decimal("2.5"),
                    squareFeet=2140,
                    description="A house.",
                )
            )
        db.commit()
        return prop.id
    finally:
        db.close()


def _purchase(session_factory, prop_id, **stamps):
    db = session_factory()
    try:
        db.add(
            PropertyPurchase(
                propertyId=prop_id, purchasePrice=Decimal("485000.00"), closingDate=date(2026, 12, 18), **stamps
            )
        )
        db.commit()
    finally:
        db.close()


def _owner(session_factory, prop_id, email, down_payment):
    db = session_factory()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(name=email.split("@")[0], email=email, passwordHash=unusable_password_hash())
            db.add(user)
            db.flush()
        db.add(UserProperty(userId=user.id, propertyId=prop_id, downPaymentAmount=down_payment))
        db.commit()
    finally:
        db.close()


def _get(client, token, prop_id, suffix=""):
    return client.get(f"{URL}/{prop_id}{suffix}", headers=bearer(token))


def test_no_purchase_row_gives_listed_stage_and_null_terms(client, officer, session_factory):
    prop_id = _seed(session_factory, UUID(officer["institution"]["id"]), loan=False)
    body = _get(client, officer["accessToken"], prop_id).json()
    assert body["purchase"] == {
        "stage": "listed",
        "purchasePrice": None,
        "closingDate": None,
        "applicationFiledAt": None,
        "intentToProceedAt": None,
        "closedAt": None,
        "interestRatePercent": None,
        "termMonths": None,
    }
    assert body["listing"] is None


@pytest.mark.parametrize(
    "stamps, stage",
    [
        ({}, "listed"),
        ({"applicationFiledAt": T1}, "application_filed"),
        ({"applicationFiledAt": T1, "intentToProceedAt": T2}, "intent_to_proceed"),
        ({"applicationFiledAt": T1, "intentToProceedAt": T2, "closedAt": T3}, "closed"),
    ],
)
def test_purchase_at_each_stage(client, officer, session_factory, stamps, stage):
    prop_id = _seed(session_factory, UUID(officer["institution"]["id"]))
    _purchase(session_factory, prop_id, **stamps)
    purchase = _get(client, officer["accessToken"], prop_id).json()["purchase"]
    assert purchase["stage"] == stage
    assert purchase["purchasePrice"] == "485000.00"
    assert purchase["closingDate"] == "2026-12-18"
    assert purchase["interestRatePercent"] == "6.250"
    assert purchase["termMonths"] == 360
    for field, stamp in (("applicationFiledAt", "applicationFiledAt"), ("intentToProceedAt", "intentToProceedAt")):
        if stamp in stamps:
            assert purchase[field].startswith(stamps[stamp].strftime("%Y-%m-%d"))
        else:
            assert purchase[field] is None
    assert (purchase["closedAt"] is not None) == (stage == "closed")


def test_loan_terms_unset_are_null(client, officer, session_factory):
    prop_id = _seed(session_factory, UUID(officer["institution"]["id"]))
    db = session_factory()
    try:
        loan = db.query(Loan).filter(Loan.propertyId == prop_id).one()
        loan.interestRatePercent = None
        loan.termMonths = None
        db.commit()
    finally:
        db.close()
    _purchase(session_factory, prop_id)
    purchase = _get(client, officer["accessToken"], prop_id).json()["purchase"]
    assert purchase["interestRatePercent"] is None and purchase["termMonths"] is None


def test_listing_summary(client, officer, session_factory):
    prop_id = _seed(session_factory, UUID(officer["institution"]["id"]), listing=True)
    assert _get(client, officer["accessToken"], prop_id).json()["listing"] == {
        "askingPrice": "489000.00",
        "bedrooms": 4,
        "bathrooms": "2.5",
        "squareFeet": 2140,
        "description": "A house.",
    }


def test_three_owners_split_the_monthly_payment(client, officer, session_factory):
    prop_id = _seed(session_factory, UUID(officer["institution"]["id"]))
    for email, amount in (("a@example.com", 80000), ("b@example.com", 50000), ("c@example.com", 30000)):
        _owner(session_factory, prop_id, email, amount)
    owners = {o["email"]: o for o in _get(client, officer["accessToken"], prop_id, "/owners").json()["owners"]}
    assert {e: (o["downPaymentAmount"], o["sharePercent"], o["estimatedMonthlyShare"]) for e, o in owners.items()} == {
        "a@example.com": ("80000.00", "50.00", "1000.54"),
        "b@example.com": ("50000.00", "31.25", "625.34"),
        "c@example.com": ("30000.00", "18.75", "375.20"),
    }
    assert sum(Decimal(o["estimatedMonthlyShare"]) for o in owners.values()) == Decimal("2001.08")


def test_unset_down_payment_gives_null_shares_not_an_error(client, officer, session_factory):
    prop_id = _seed(session_factory, UUID(officer["institution"]["id"]))
    _owner(session_factory, prop_id, "a@example.com", 80000)
    _owner(session_factory, prop_id, "b@example.com", None)
    resp = _get(client, officer["accessToken"], prop_id, "/owners")
    assert resp.status_code == 200, resp.text
    by_email = {o["email"]: o for o in resp.json()["owners"]}
    assert by_email["a@example.com"]["downPaymentAmount"] == "80000.00"
    assert by_email["b@example.com"]["downPaymentAmount"] is None
    for o in by_email.values():
        assert o["sharePercent"] is None and o["estimatedMonthlyShare"] is None


@pytest.mark.parametrize("suffix", ["", "/owners"])
def test_access_rules_are_unchanged(client, officer, session_factory, suffix):
    mine = _seed(session_factory, UUID(officer["institution"]["id"]))
    token = _buyer(client).token
    assert _get(client, token, mine, suffix).status_code == 403  # unlinked buyer
    assert _get(client, officer["accessToken"], uuid4(), suffix).status_code == 404
    assert _get(client, officer["accessToken"], "not-a-uuid", suffix).status_code == 404
    assert _get(client, officer["accessToken"], mine, suffix).status_code == 200  # the owning institution's officer
    other = _second_officer(client)
    assert _get(client, other["accessToken"], mine, suffix).status_code == 403  # another institution's officer


def test_linked_buyer_reads_the_purchase(client, officer, session_factory):
    prop_id = _seed(session_factory, UUID(officer["institution"]["id"]))
    _purchase(session_factory, prop_id, applicationFiledAt=T1)
    token = _buyer(client).token
    _owner(session_factory, prop_id, "buyer1@example.com", 1000)
    resp = _get(client, token, prop_id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["purchase"]["stage"] == "application_filed"


def test_only_additive_keys(client, officer, session_factory):
    prop_id = _seed(session_factory, UUID(officer["institution"]["id"]))
    _owner(session_factory, prop_id, "a@example.com", 1000)
    detail = _get(client, officer["accessToken"], prop_id).json()
    assert set(detail) == {"property", "agreement", "purchase", "listing"}
    assert set(detail["property"]) == {
        "id", "institutionId", "address", "loanAmount", "currentBalance", "monthlyPayment",
        "dynamicBillingEnabled", "status", "createdAt",
    }  # fmt: skip
    assert set(detail["agreement"]) == {
        "id", "propertyId", "noticeDays", "valuationMethod", "partialClaimMethod", "effectiveAt",
    }  # fmt: skip
    owners = _get(client, officer["accessToken"], prop_id, "/owners").json()
    assert set(owners) == {"owners"}
    assert set(owners["owners"][0]) == {
        "userPropertyId", "userId", "name", "email", "maxOwnershipPercent", "signedAt",
        "downPaymentAmount", "sharePercent", "estimatedMonthlyShare",
    }  # fmt: skip

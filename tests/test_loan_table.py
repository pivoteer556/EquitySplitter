from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Loan, Property
from tests.conftest import bearer
from tests.test_property_flow import _property

API = "/api/v1"


def _loans(session_factory, prop_id):
    with session_factory() as db:
        return [
            (x.loanAmount, x.currentBalance, x.monthlyPayment, x.dynamicBillingEnabled)
            for x in db.query(Loan).filter(Loan.propertyId == UUID(prop_id)).all()
        ]


def _patch(client, officer, prop_id, body):
    resp = client.patch(f"{API}/properties/{prop_id}", json=body, headers=bearer(officer["accessToken"]))
    assert resp.status_code == 200, resp.text


def test_create_property_writes_one_loan(client, officer, session_factory):
    prop = _property(client, officer)
    assert _loans(session_factory, prop["id"]) == [(Decimal("300000"), Decimal("250000"), Decimal("1800"), False)]


def test_patch_mirrors_loan_fields_and_keeps_the_rest(client, officer, session_factory):
    prop = _property(client, officer)
    _patch(client, officer, prop["id"], {"currentBalance": "100", "dynamicBillingEnabled": True})
    assert _loans(session_factory, prop["id"]) == [(Decimal("300000"), Decimal("100"), Decimal("1800"), True)]
    _patch(client, officer, prop["id"], {"loanAmount": "400000", "monthlyPayment": "2000"})
    assert _loans(session_factory, prop["id"]) == [(Decimal("400000"), Decimal("100"), Decimal("2000"), True)]


def test_patch_address_only_leaves_loan(client, officer, session_factory):
    prop = _property(client, officer)
    before = _loans(session_factory, prop["id"])
    _patch(client, officer, prop["id"], {"address": "2 Elm St"})
    assert _loans(session_factory, prop["id"]) == before


def test_patch_creates_missing_loan_from_current_values(client, officer, session_factory):
    prop = _property(client, officer)
    with session_factory() as db:
        db.query(Loan).delete()
        db.commit()
    _patch(client, officer, prop["id"], {"address": "2 Elm St"})
    assert _loans(session_factory, prop["id"]) == [(Decimal("300000"), Decimal("250000"), Decimal("1800"), False)]


def test_deleting_property_cascades_loan(client, officer, session_factory):
    prop = _property(client, officer)
    with session_factory() as db:
        db.delete(db.get(Property, UUID(prop["id"])))
        db.commit()
        assert db.query(Loan).count() == 0


def test_second_loan_for_property_violates_uniqueness(client, officer, session_factory):
    prop = _property(client, officer)
    with session_factory() as db, pytest.raises(IntegrityError):
        db.add(Loan(propertyId=UUID(prop["id"]), loanAmount=1, currentBalance=1, monthlyPayment=1))
        db.commit()

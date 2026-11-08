from decimal import Decimal
from uuid import UUID

from sqlalchemy import event

from app.models import Loan
from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_property_flow import _property
from tests.test_property_list import _owner_token

API = "/api/v1"
PROPERTY_KEYS = {
    "id",
    "institutionId",
    "address",
    "loanAmount",
    "currentBalance",
    "monthlyPayment",
    "dynamicBillingEnabled",
    "status",
    "createdAt",
}
# _property() creates 300000 / 250000 / 1800 / False; the Loan row is made to differ from that.
LOAN_VALUES = {
    "loanAmount": "111.00",
    "currentBalance": "22.00",
    "monthlyPayment": "3.00",
    "dynamicBillingEnabled": True,
}


def _diverge_loan(session_factory, prop_id):
    with session_factory() as db:
        loan = db.query(Loan).filter(Loan.propertyId == UUID(prop_id)).one()
        loan.loanAmount = Decimal("111")
        loan.currentBalance = Decimal("22")
        loan.monthlyPayment = Decimal("3")
        loan.dynamicBillingEnabled = True
        db.commit()


def _loan_fields(body):
    return {k: body[k] for k in LOAN_VALUES}


def _as_loan(body):
    assert set(body) == PROPERTY_KEYS
    got = _loan_fields(body)
    assert {k: Decimal(str(v)) for k, v in got.items() if k != "dynamicBillingEnabled"} == {
        k: Decimal(v) for k, v in LOAN_VALUES.items() if k != "dynamicBillingEnabled"
    }
    assert got["dynamicBillingEnabled"] is True


def _get(client, token, url):
    resp = client.get(url, headers=bearer(token))
    assert resp.status_code == 200, resp.text
    return resp.json(), resp.headers.get("X-Refreshed-Token", token)


def test_officer_detail_reads_loan_row(client, officer, session_factory):
    prop = _property(client, officer)
    _diverge_loan(session_factory, prop["id"])
    body, _ = _get(client, officer["accessToken"], f"{API}/properties/{prop['id']}")
    assert set(body) == {"property", "agreement"}
    _as_loan(body["property"])


def test_owner_detail_reads_loan_row(client, officer, session_factory):
    prop, invite = _invited(client, officer)
    token = _owner_token(client, invite)
    _diverge_loan(session_factory, prop["id"])
    body, _ = _get(client, token, f"{API}/properties/{prop['id']}")
    _as_loan(body["property"])


def test_list_reads_loan_row_for_officer_and_owner(client, officer, session_factory):
    prop, invite = _invited(client, officer)
    token = _owner_token(client, invite)
    _diverge_loan(session_factory, prop["id"])
    body, _ = _get(client, token, f"{API}/properties")
    assert len(body) == 1
    _as_loan(body[0])
    body, _ = _get(client, officer["accessToken"], f"{API}/properties")
    assert len(body) == 1
    _as_loan(body[0])


def test_list_does_not_query_loans_per_property(client, officer, session_factory):
    for _ in range(3):
        _property(client, officer)
    statements = []

    def count(conn, cursor, statement, *args):
        if "FROM loans" in statement:
            statements.append(statement)

    engine = session_factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", count)
    try:
        body, _ = _get(client, officer["accessToken"], f"{API}/properties")
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert len(body) == 3
    assert len(statements) == 1


def test_patch_unrelated_field_responds_from_loan_and_keeps_it(client, officer, session_factory):
    prop = _property(client, officer)
    _diverge_loan(session_factory, prop["id"])
    resp = client.patch(
        f"{API}/properties/{prop['id']}", json={"address": "9 New Rd"}, headers=bearer(officer["accessToken"])
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["address"] == "9 New Rd"
    _as_loan(resp.json())
    with session_factory() as db:  # the unrelated PATCH must not overwrite the loan row with legacy values
        loan = db.query(Loan).one()
        assert loan.loanAmount == Decimal("111")


def test_patch_loan_field_writes_both_and_responds_from_loan(client, officer, session_factory):
    prop = _property(client, officer)
    resp = client.patch(
        f"{API}/properties/{prop['id']}", json={"currentBalance": "200000"}, headers=bearer(officer["accessToken"])
    )
    assert resp.status_code == 200, resp.text
    assert Decimal(str(resp.json()["currentBalance"])) == Decimal("200000")
    with session_factory() as db:
        from app.models import Property

        assert db.get(Property, UUID(prop["id"])).currentBalance == Decimal("200000")
        assert db.query(Loan).one().currentBalance == Decimal("200000")


def test_missing_loan_row_falls_back_to_legacy_columns(client, officer, session_factory):
    prop = _property(client, officer)
    with session_factory() as db:
        db.query(Loan).delete()
        db.commit()
    for url in (f"{API}/properties/{prop['id']}", f"{API}/properties"):
        body, _ = _get(client, officer["accessToken"], url)
        row = body["property"] if "property" in body else body[0]
        assert set(row) == PROPERTY_KEYS
        assert Decimal(str(row["loanAmount"])) == Decimal("300000")
        assert row["dynamicBillingEnabled"] is False

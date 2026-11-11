"""An email is normalized (stripped, lowercased) the same way everywhere it enters the system, so an officer or owner
created as `Casey@Example.com` can sign in with either casing and is never a second row for the same person."""

import importlib
import inspect
import pkgutil
from uuid import UUID

import pytest
from pydantic import BaseModel, TypeAdapter

import app.schemas
from app.models import InstitutionUser, Property, PropertyAgreement, User, UserProperty
from tests.conftest import bearer
from tests.test_officer_activation import API, _activate, _login

MIXED = "Casey.Mixed@Example.COM"
LOWER = "casey.mixed@example.com"


def _create(client, officer, email):
    return client.post(
        f"{API}/institution-users",
        json={"institutionId": officer["institution"]["id"], "name": "Mixed Case", "email": email},
        headers=bearer(officer["accessToken"]),
    )


def test_officer_created_with_mixed_case_is_stored_lowercase_and_signs_in_either_way(client, officer, session_factory):
    created = _create(client, officer, MIXED)
    assert created.status_code == 201, created.text
    assert created.json()["email"] == LOWER
    db = session_factory()
    try:
        assert [r.email for r in db.query(InstitutionUser).filter(InstitutionUser.name == "Mixed Case")] == [LOWER]
    finally:
        db.close()
    assert _activate(client, created.json()["activationToken"]).status_code == 200
    assert _login(client, email=MIXED).status_code == 200
    assert _login(client, email=LOWER).status_code == 200


def test_same_officer_email_in_another_casing_is_a_409(client, officer):
    assert _create(client, officer, MIXED).status_code == 201
    again = _create(client, officer, MIXED.upper().replace("@EXAMPLE.COM", "@example.com"))
    assert again.status_code == 409
    assert again.json()["detail"] == "Email already registered"


def test_inviting_an_owner_in_two_casings_is_one_user(client, officer, session_factory):
    db = session_factory()
    try:
        prop = Property(
            institutionId=UUID(officer["institution"]["id"]),
            address="1 Main St",
            loanAmount=1,
            currentBalance=1,
            monthlyPayment=1,
            status="pending_acknowledgement",
        )
        db.add(prop)
        db.flush()
        agreement = {"noticeDays": 30, "valuationMethod": "appraisal", "partialClaimMethod": "pro_rata"}
        db.add(PropertyAgreement(propertyId=prop.id, **agreement))
        db.commit()
        url = f"{API}/properties/{prop.id}/owners"
    finally:
        db.close()
    token = officer["accessToken"]
    for email in ("Olive@Example.com", "olive@example.com"):
        resp = client.post(url, json={"name": "Olive Owner", "email": email}, headers=bearer(token))
        assert resp.status_code == 201, resp.text
        token = resp.headers.get("X-Refreshed-Token", token)
    db = session_factory()
    try:
        assert [u.email for u in db.query(User).filter(User.name == "Olive Owner")] == ["olive@example.com"]
        assert db.query(UserProperty).count() == 1
    finally:
        db.close()


def _request_email_fields():
    """Every email field on a request model (name ends in Create or Request) in any app.schemas module. Response
    models are left alone: they read emails back from the database."""
    found = []
    for info in pkgutil.iter_modules(app.schemas.__path__):
        module = importlib.import_module(f"app.schemas.{info.name}")
        for name, cls in inspect.getmembers(module, inspect.isclass):
            is_request = name.endswith(("Create", "Request"))
            if cls.__module__ != module.__name__ or not issubclass(cls, BaseModel) or not is_request:
                continue
            for field, finfo in cls.model_fields.items():
                if field == "email" or field.endswith("Email"):
                    found.append(pytest.param(finfo, id=f"{name}.{field}"))
    return found


def test_the_guard_finds_the_known_request_schemas():
    ids = {p.id for p in _request_email_fields()}
    assert {"AuthRegisterRequest.email", "AuthLoginRequest.email", "InstitutionBootstrapRequest.officerEmail"} <= ids
    assert {"InstitutionUserCreate.email", "OwnerInviteCreate.email"} <= ids


@pytest.mark.parametrize("finfo", _request_email_fields())
def test_every_request_email_field_normalizes(finfo):
    assert TypeAdapter(finfo.rebuild_annotation()).validate_python("  Casey@Example.COM ") == "casey@example.com"

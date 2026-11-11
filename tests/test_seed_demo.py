import re

import pytest

from app.models import (
    Institution,
    OwnerAcknowledgement,
    Property,
    PropertyAgreement,
    PropertyListing,
    PropertyPurchase,
    User,
    UserProperty,
)
from app.services.purchase import PurchaseStage, purchase_stage
from scripts.seed_demo import main
from scripts.seed_demo_data import ADDRESS, BUYERS
from tests.conftest import STRONG_PASSWORD, bearer

LINK = re.compile(r"(\S+)/accept-invite#token=(\S+)")
EMAILS = [b.email for b in BUYERS]
MODELS = (Institution, Property, PropertyPurchase, PropertyAgreement, PropertyListing, User, UserProperty)
MODELS += (OwnerAcknowledgement,)


def _run(session_factory, capsys, *args):
    code = main(["--yes", *args], session_factory)
    out = capsys.readouterr()
    return code, out.out, out.err


def _counts(session_factory):
    with session_factory() as db:
        return [db.query(m).count() for m in MODELS]


def _links(out):
    return {m.group(2): m.group(1) for m in LINK.finditer(out)}


def test_seeds_the_full_graph(session_factory, capsys):
    code, _, _ = _run(session_factory, capsys)
    assert code == 0
    with session_factory() as db:
        prop = db.query(Property).filter(Property.address == ADDRESS).one()
        assert prop.status == "pending_acknowledgement"
        assert (float(prop.loan.loanAmount), float(prop.loan.monthlyPayment)) == (325000.0, 2001.08)
        assert (float(prop.loan.interestRatePercent), prop.loan.termMonths) == (6.25, 360)
        assert float(prop.purchase.purchasePrice) == 485000.0
        assert prop.purchase.applicationFiledAt and prop.purchase.intentToProceedAt
        assert purchase_stage(prop.purchase) == PurchaseStage.INTENT_TO_PROCEED
        listing = db.query(PropertyListing).filter(PropertyListing.propertyId == prop.id).one()
        assert (listing.status, listing.bedrooms, listing.squareFeet) == ("listed", 4, 2140)
        assert listing.description and "not a real property" in listing.description
        agreement = prop.agreement
        assert agreement.noticeDays == 60 and agreement.effectiveAt is None
        links = db.query(UserProperty).filter(UserProperty.propertyId == prop.id).all()
        assert sorted(float(link.downPaymentAmount) for link in links) == [30000.0, 50000.0, 80000.0]
        acks = db.query(OwnerAcknowledgement).all()
        assert len(acks) == 3 and all(a.signedAt is None for a in acks)
        users = db.query(User).all()
        assert sorted(u.email for u in users) == sorted(EMAILS)
        assert all(u.passwordSetAt is None for u in users)


def test_stage_application_sets_only_the_application(session_factory, capsys):
    _run(session_factory, capsys, "--stage", "application")
    with session_factory() as db:
        prop = db.query(Property).one()
        assert prop.purchase.applicationFiledAt is not None
        assert prop.purchase.intentToProceedAt is None
        assert purchase_stage(prop.purchase) == PurchaseStage.APPLICATION_FILED


def test_never_writes_closed_at(session_factory, capsys):
    _run(session_factory, capsys)
    with session_factory() as db:
        assert db.query(PropertyPurchase).one().closedAt is None


def test_rerun_is_idempotent_and_reissues_links_for_unset_accounts(session_factory, capsys):
    _, first, _ = _run(session_factory, capsys)
    before = _counts(session_factory)
    assert before == [1, 1, 1, 1, 1, 3, 3, 3]
    _, second, _ = _run(session_factory, capsys)
    assert _counts(session_factory) == before
    assert len(_links(first)) == 3 and len(_links(second)) == 3


def test_stage_never_rewinds_an_existing_purchase(session_factory, capsys):
    _run(session_factory, capsys)
    _run(session_factory, capsys, "--stage", "application")
    with session_factory() as db:
        assert db.query(PropertyPurchase).one().intentToProceedAt is not None


def test_buyer_with_password_set_gets_no_new_link(client, session_factory, capsys):
    _, out, _ = _run(session_factory, capsys)
    token = next(iter(_links(out)))
    body = {"token": token, "password": STRONG_PASSWORD}
    assert client.post("/api/v1/auth/accept-invite", json=body).status_code == 200
    _, out, _ = _run(session_factory, capsys)
    assert len(_links(out)) == 2
    assert "already set up" in out


def test_link_sets_password_then_signin_and_property_read_work(client, session_factory, capsys):
    _, out, _ = _run(session_factory, capsys, "--base-url", "https://demo.example.test/")
    links = _links(out)
    assert set(links.values()) == {"https://demo.example.test"}
    for line in out.splitlines():
        if line.startswith(BUYERS[0].email + ":"):
            token = LINK.search(line).group(2)
    accepted = client.post("/api/v1/auth/accept-invite", json={"token": token, "password": STRONG_PASSWORD})
    assert accepted.status_code == 200, accepted.text
    login = client.post("/api/v1/auth/login", json={"email": BUYERS[0].email, "password": STRONG_PASSWORD})
    assert login.status_code == 200, login.text
    with session_factory() as db:
        prop_id = str(db.query(Property).one().id)
    got = client.get(f"/api/v1/properties/{prop_id}", headers=bearer(login.json()["accessToken"]))
    assert got.status_code == 200, got.text
    assert got.json()["property"]["address"] == ADDRESS


def test_default_base_url(session_factory, capsys):
    _, out, _ = _run(session_factory, capsys)
    assert set(_links(out).values()) == {"https://equitysplitter.app"}


def test_takes_and_prints_no_password(session_factory, capsys):
    with pytest.raises(SystemExit):
        main(["--yes", "--password", "x"], session_factory)
    capsys.readouterr()
    _, out, err = _run(session_factory, capsys)
    assert "$argon2" not in out + err
    assert STRONG_PASSWORD not in out + err


def test_refuses_to_write_without_yes(session_factory, capsys):
    code = main([], session_factory)
    out = capsys.readouterr()
    assert code != 0 and "--yes" in out.err
    assert _counts(session_factory) == [0] * len(MODELS)
    assert not LINK.search(out.out)


def test_prints_target_host_and_database_but_no_credentials(session_factory, capsys):
    _, out, err = _run(session_factory, capsys)
    assert "Target database:" in out + err
    assert "postgres:" not in out + err


def test_dry_run_writes_nothing(session_factory, capsys):
    code = main(["--dry-run"], session_factory)
    out = capsys.readouterr()
    assert code == 0 and "would" in out.out.lower()
    assert _counts(session_factory) == [0] * len(MODELS)
    assert not LINK.search(out.out)


def test_refuses_without_database_url_in_environment(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    code = main(["--yes"])
    assert code != 0 and "DATABASE_URL" in capsys.readouterr().err

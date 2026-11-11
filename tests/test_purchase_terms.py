from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Institution, Loan, Property, PropertyPurchase, User, UserProperty

FILED = datetime(2026, 3, 1, tzinfo=UTC)
ITP = datetime(2026, 4, 1, tzinfo=UTC)
CLOSED = datetime(2026, 6, 1, tzinfo=UTC)


def _property(db):
    inst = Institution(name="Bank")
    db.add(inst)
    db.flush()
    prop = Property(institutionId=inst.id, address="1 Oak St", loanAmount=1, currentBalance=1, monthlyPayment=1)
    db.add(prop)
    db.flush()
    return prop


def _purchase(prop, **kw):
    return PropertyPurchase(propertyId=prop.id, purchasePrice=kw.pop("purchasePrice", Decimal("400000.00")), **kw)


def test_purchase_persists_with_all_fields(session_factory):
    with session_factory() as db:
        prop = _property(db)
        db.add(
            _purchase(
                prop,
                closingDate=date(2026, 6, 15),
                applicationFiledAt=FILED,
                intentToProceedAt=ITP,
                closedAt=CLOSED,
            )
        )
        db.commit()
        got = db.query(PropertyPurchase).one()
        assert got.purchasePrice == Decimal("400000.00")
        assert got.closingDate == date(2026, 6, 15)
        assert got.applicationFiledAt is not None
        assert got.intentToProceedAt is not None
        assert got.closedAt is not None
        assert got.createdAt is not None
        assert prop.purchase is got


def test_loan_rate_and_term_persist(session_factory):
    with session_factory() as db:
        prop = _property(db)
        db.add(
            Loan(
                propertyId=prop.id,
                loanAmount=1,
                currentBalance=1,
                monthlyPayment=1,
                interestRatePercent=Decimal("6.250"),
                termMonths=360,
            )
        )
        db.commit()
        loan = db.query(Loan).one()
        assert (loan.interestRatePercent, loan.termMonths) == (Decimal("6.250"), 360)


def test_down_payment_persists(session_factory):
    with session_factory() as db:
        prop = _property(db)
        user = User(name="A", email="a@example.com", passwordHash="x")
        db.add(user)
        db.flush()
        db.add(UserProperty(userId=user.id, propertyId=prop.id, downPaymentAmount=Decimal("80000.00")))
        db.commit()
        assert db.query(UserProperty).one().downPaymentAmount == Decimal("80000.00")


def test_deleting_property_cascades_purchase(session_factory):
    with session_factory() as db:
        prop = _property(db)
        db.add(_purchase(prop))
        db.commit()
        db.delete(prop)
        db.commit()
        assert db.query(PropertyPurchase).count() == 0


@pytest.mark.parametrize(
    "fields",
    [
        {"purchasePrice": Decimal("0")},
        {"purchasePrice": Decimal("-1")},
        {"intentToProceedAt": ITP},
        {"applicationFiledAt": FILED, "closedAt": CLOSED},
        {"closedAt": CLOSED},
    ],
    ids=["zero price", "negative price", "itp without application", "closed without itp", "closed alone"],
)
def test_check_constraints_reject_bad_rows(session_factory, fields):
    with session_factory() as db:
        prop = _property(db)
        db.add(_purchase(prop, **fields))
        with pytest.raises(IntegrityError):
            db.commit()


def test_second_purchase_for_a_property_is_rejected(session_factory):
    with session_factory() as db:
        prop = _property(db)
        db.add(_purchase(prop))
        db.commit()
        db.add(_purchase(prop))
        with pytest.raises(IntegrityError):
            db.commit()

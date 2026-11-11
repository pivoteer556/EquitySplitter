"""Operator script: seed the fictional demo house and its three co-buyers. Takes NO password.

    DATABASE_URL=... python -m scripts.seed_demo --yes [--stage application|itp] [--base-url URL] [--dry-run]

Writes one fictional institution, house, loan, purchase, agreement, listing and three buyers (example.com emails),
then prints a one-time set-password link per buyer whose password is still unset, from the same generator as owner
invites (issue_invite_token). Nobody picks or knows anyone's password but the person who opens a link (backlog
2c-1). Idempotent: rows are found by natural keys (address, email); a re-run adds nothing, never rewinds a stage and
issues links only for accounts that have not set a password. The agreement and signed acknowledgements are immutable
by database trigger, so they are inserted once, unsigned, and never updated. `closedAt` is never written.

It refuses to run without DATABASE_URL in the environment, prints the host and database it will write to (never
credentials) and writes only with --yes. --dry-run runs everything in a transaction that is rolled back.
"""

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    Institution,
    Loan,
    OwnerAcknowledgement,
    Property,
    PropertyAgreement,
    PropertyListing,
    PropertyPurchase,
    User,
    UserProperty,
)
from app.schemas.types import normalize_email
from app.services.auth import issue_invite_token, unusable_password_hash
from scripts import seed_demo_data as data

DEFAULT_BASE_URL = "https://equitysplitter.app"
STAGES = ("application", "itp")


class Run:
    """One seeding run: the session and the lines it reports (what was created, what already existed)."""

    def __init__(self, db: Session, dry_run: bool) -> None:
        self.db = db
        self.dry_run = dry_run
        self.lines: list[str] = []

    def get_or_create(self, model: type, label: str, keys: dict[str, Any], defaults: dict[str, Any]) -> Any:
        row = self.db.query(model).filter_by(**keys).first()
        if row is not None:
            self.lines.append(f"exists: {label}")
            return row
        row = model(**keys, **defaults)
        self.db.add(row)
        self.db.flush()
        self.lines.append(f"{'would create' if self.dry_run else 'created'}: {label}")
        return row


def _seed_house(run: Run) -> Property:
    inst = run.get_or_create(Institution, "institution", {"name": data.INSTITUTION_NAME}, {})
    # The legacy property loan columns are NOT NULL and mirror the Loan row, as POST /properties writes them.
    loan_fields = {
        "loanAmount": data.LOAN_AMOUNT,
        "currentBalance": data.LOAN_AMOUNT,
        "monthlyPayment": data.MONTHLY_PAYMENT,
    }
    prop = run.get_or_create(
        Property,
        "property",
        {"institutionId": inst.id, "address": data.ADDRESS},
        {**loan_fields, "status": "pending_acknowledgement"},
    )
    loan_terms = {"interestRatePercent": data.INTEREST_RATE_PERCENT, "termMonths": data.TERM_MONTHS}
    run.get_or_create(Loan, "loan", {"propertyId": prop.id}, {**loan_fields, **loan_terms})
    return prop


def _seed_purchase(run: Run, prop: Property, stage: str) -> None:
    purchase = run.get_or_create(
        PropertyPurchase,
        "purchase",
        {"propertyId": prop.id},
        {"purchasePrice": data.PURCHASE_PRICE, "closingDate": data.CLOSING_DATE},
    )
    # Set-if-null: a stage is only ever advanced, never rewound. closedAt is deliberately never written.
    if purchase.applicationFiledAt is None:
        purchase.applicationFiledAt = data.APPLICATION_FILED_AT
    if stage == "itp" and purchase.intentToProceedAt is None:
        purchase.intentToProceedAt = data.INTENT_TO_PROCEED_AT
    run.db.flush()


def _seed_listing_and_agreement(run: Run, prop: Property) -> PropertyAgreement:
    listing = {
        "askingPrice": data.LISTING_ASKING_PRICE,
        "bedrooms": data.LISTING_BEDROOMS,
        "bathrooms": data.LISTING_BATHROOMS,
        "squareFeet": data.LISTING_SQUARE_FEET,
        "description": data.LISTING_DESCRIPTION,
        "listedAt": data.LISTING_LISTED_AT,
    }
    run.get_or_create(PropertyListing, "listing", {"propertyId": prop.id, "status": "listed"}, listing)
    agreement = {
        "noticeDays": data.NOTICE_DAYS,
        "valuationMethod": data.VALUATION_METHOD,
        "partialClaimMethod": data.PARTIAL_CLAIM_METHOD,
    }
    return run.get_or_create(PropertyAgreement, "agreement", {"propertyId": prop.id}, agreement)


def _seed_buyer(run: Run, prop: Property, agreement: PropertyAgreement, buyer: data.Buyer) -> User:
    # Same rows as invite_owner: a password-less user, the property link, and an unsigned acknowledgement.
    email = normalize_email(buyer.email)
    user = run.get_or_create(
        User, f"buyer {email}", {"email": email}, {"name": buyer.name, "passwordHash": unusable_password_hash()}
    )
    link_keys = {"userId": user.id, "propertyId": prop.id}
    link = run.get_or_create(UserProperty, f"link {email}", link_keys, {"downPaymentAmount": buyer.downPayment})
    run.get_or_create(
        OwnerAcknowledgement, f"acknowledgement {email}", {"agreementId": agreement.id, "userPropertyId": link.id}, {}
    )
    return user


def seed(run: Run, stage: str) -> list[User]:
    prop = _seed_house(run)
    _seed_purchase(run, prop, stage)
    agreement = _seed_listing_and_agreement(run, prop)
    return [_seed_buyer(run, prop, agreement, buyer) for buyer in data.BUYERS]


def _target(db: Session) -> str:
    url = db.get_bind().engine.url  # host and database only: never the user or password
    return f"host={url.host or '<none>'} database={url.database or '<none>'}"


def _report_links(db: Session, users: list[User], base_url: str) -> None:
    base = base_url.rstrip("/")
    for user in users:
        if user.passwordSetAt is not None:
            print(f"{user.email}: already set up, no new link")
        else:
            print(f"{user.email}: {base}/accept-invite#token={issue_invite_token(db, user.id)}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seed_demo", description="Seed the fictional demo house (no password).")
    parser.add_argument("--stage", choices=STAGES, default="itp", help="itp (default) or application only")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--yes", action="store_true", help="confirm writing to the target database")
    parser.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    return parser


def main(argv: Sequence[str] | None = None, db_factory: Callable[[], Session] | None = None) -> int:
    args = _parser().parse_args(argv)
    if db_factory is None:
        if not os.environ.get("DATABASE_URL"):
            print("Refusing to run: set DATABASE_URL explicitly to the target database.", file=sys.stderr)
            return 1
        from app.db.session import SessionLocal

        db_factory = SessionLocal
    with db_factory() as db:
        print(f"Target database: {_target(db)}")
        if not (args.dry_run or args.yes):
            print("Refusing to write without --yes (use --dry-run to preview).", file=sys.stderr)
            return 1
        run = Run(db, args.dry_run)
        users = seed(run, args.stage)
        print("\n".join(run.lines))
        if args.dry_run:
            db.rollback()
            print("Dry run: nothing written, no links issued.")
            return 0
        db.commit()
        _report_links(db, users, args.base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Operator script: create (or re-issue the link for) a platform admin. Takes NO password.

    python -m scripts.create_platform_admin <email>

Prints a one-time set-password link from the same generator as owner invites; only the account holder ever knows
the password (backlog 2c-1). A re-run never changes a password. Run against a real database only deliberately.
"""

import argparse
import sys
from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

from app.models import User
from app.services.auth import create_platform_admin


def main(argv: Sequence[str] | None = None, db_factory: Callable[[], Session] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="create_platform_admin", description="Create a platform admin (no password).")
    parser.add_argument("email")
    args = parser.parse_args(argv)
    if db_factory is None:
        from app.db.session import SessionLocal

        db_factory = SessionLocal
    with db_factory() as db:
        try:
            token = create_platform_admin(db, args.email)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        already_set = db.query(User).filter(User.email == args.email.strip()).one().passwordSetAt is not None
    if already_set:
        print("Note: this admin already chose a credential; the link below is refused (single use).", file=sys.stderr)
    print(f"/accept-invite#token={token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

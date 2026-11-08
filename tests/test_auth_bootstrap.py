from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.services.auth import bootstrap_institution, decode_token


def test_bootstrap_institution_issues_activation_token(tmp_path: Path):
    db_path = tmp_path / "auth.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    db = SessionLocal()
    try:
        institution, officer, token = bootstrap_institution(
            db,
            institution_name="Atlas Lending",
            officer_name="Casey Officer",
            officer_email="casey.officer@example.com",
        )

        claims = decode_token(db, token)

        assert institution.id is not None
        assert officer.id is not None
        assert officer.institutionId == institution.id
        assert claims["userType"] == "institution_invite"
        assert officer.passwordSetAt is None
        assert claims["sub"] == str(officer.id)
    finally:
        db.close()

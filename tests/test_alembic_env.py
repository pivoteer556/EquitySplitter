from alembic import command
from alembic.config import Config
from app.core.config import settings


def test_database_url_with_percent_encoding_reaches_alembic_unchanged(monkeypatch, capsys):
    url = "postgresql+psycopg://u:p%40ss@h/db"
    monkeypatch.setattr(settings, "database_url", url)
    cfg = Config("alembic.ini")

    # Offline mode renders SQL without connecting, so it runs env.py with no database.
    command.upgrade(cfg, "head", sql=True)

    assert cfg.get_main_option("sqlalchemy.url") == url
    capsys.readouterr()


def test_offline_render_adds_and_backfills_institution_password_set_at(capsys):
    command.upgrade(Config("alembic.ini"), "0007_connection_requests:0008_institution_password_set_at", sql=True)
    sql = capsys.readouterr().out
    assert 'ADD COLUMN "passwordSetAt"' in sql
    assert 'UPDATE "institutionUsers" SET "passwordSetAt"' in sql


def test_offline_render_creates_property_listings_with_one_listed_per_property(capsys):
    command.upgrade(Config("alembic.ini"), "0008_institution_password_set_at:0009_property_listings", sql=True)
    sql = capsys.readouterr().out
    assert 'CREATE TABLE "propertyListings"' in sql
    assert "CREATE UNIQUE INDEX" in sql and "WHERE status = 'listed'" in sql


def test_offline_render_creates_totp_credentials_one_per_user(capsys):
    command.upgrade(Config("alembic.ini"), "0009_property_listings:0010_totp_credentials", sql=True)
    sql = capsys.readouterr().out
    assert 'CREATE TABLE "totpCredentials"' in sql
    assert "UNIQUE (" in sql and '"institutionUserId"' in sql and "ON DELETE CASCADE" in sql


def test_offline_render_creates_recovery_codes_with_hash_and_cascade(capsys):
    command.upgrade(Config("alembic.ini"), "0011_user_platform_admin:0012_recovery_codes", sql=True)
    sql = capsys.readouterr().out
    assert 'CREATE TABLE "recoveryCodes"' in sql and '"codeHash"' in sql and '"usedAt"' in sql
    assert "ON DELETE CASCADE" in sql


def test_offline_render_creates_purchases_with_stage_checks_and_adds_term_columns(capsys):
    command.upgrade(Config("alembic.ini"), "0012_recovery_codes:0013_purchase_terms", sql=True)
    sql = capsys.readouterr().out
    assert 'CREATE TABLE "propertyPurchases"' in sql and "ON DELETE CASCADE" in sql
    assert '"intentToProceedAt" IS NULL OR "applicationFiledAt" IS NOT NULL' in sql
    assert '"closedAt" IS NULL OR "intentToProceedAt" IS NOT NULL' in sql
    assert 'ADD COLUMN "interestRatePercent"' in sql and 'ADD COLUMN "termMonths"' in sql
    assert 'ADD COLUMN "downPaymentAmount"' in sql


def test_offline_render_downgrade_drops_purchases_and_term_columns(capsys):
    command.downgrade(Config("alembic.ini"), "0013_purchase_terms:0012_recovery_codes", sql=True)
    sql = capsys.readouterr().out
    assert 'DROP TABLE "propertyPurchases"' in sql
    assert 'DROP COLUMN "interestRatePercent"' in sql and 'DROP COLUMN "termMonths"' in sql
    assert 'DROP COLUMN "downPaymentAmount"' in sql


def test_alembic_has_one_head_and_it_is_the_purchase_terms_migration():
    from alembic.script import ScriptDirectory

    assert ScriptDirectory.from_config(Config("alembic.ini")).get_heads() == ["0013_purchase_terms"]

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

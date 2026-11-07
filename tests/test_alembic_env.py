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

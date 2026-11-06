#!/bin/sh
set -e

# Wait for Postgres to be reachable via SQLAlchemy URL.
until python -c "from sqlalchemy import create_engine, text; from app.core.config import settings; e=create_engine(settings.database_url); c=e.connect(); c.execute(text('SELECT 1')); c.close()"; do
  echo "Waiting for database..."
  sleep 2
done

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
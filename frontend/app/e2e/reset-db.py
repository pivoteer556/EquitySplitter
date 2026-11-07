"""Drop and recreate the throwaway e2e database. Local-only: refuses any host but localhost/127.0.0.1."""
import os
import sys

import psycopg

url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
host_ok = ("@localhost:" in url) or ("@127.0.0.1:" in url)
if not host_ok or not url.endswith("/equity_e2e"):
    sys.exit(f"refusing to reset a database that is not local equity_e2e: {url.rsplit('@', 1)[-1]}")

admin_url = url.rsplit("/", 1)[0] + "/postgres"
with psycopg.connect(admin_url, autocommit=True) as conn:
    conn.execute("DROP DATABASE IF EXISTS equity_e2e WITH (FORCE)")
    conn.execute("CREATE DATABASE equity_e2e")
print("equity_e2e recreated")

"""Phase 0 check: can we reach the "washo" database with the details in .env?

Run:  venv\\Scripts\\python scripts\\check_db.py
"""
import sys

import psycopg
from decouple import config

if config("DB_PASSWORD", default="") in ("", "PUT_YOUR_DB_PASSWORD_HERE"):
    print("DB_PASSWORD is not set yet. Open .env and type the washo_user password.")
    sys.exit(1)

try:
    conn = psycopg.connect(
        dbname=config("DB_NAME"),
        user=config("DB_USER"),
        password=config("DB_PASSWORD"),
        host=config("DB_HOST", default="localhost"),
        port=config("DB_PORT", default="5432"),
    )
except psycopg.OperationalError as e:
    print("FAILED to connect. Check DB_PASSWORD (and the other DB_ values) in .env.")
    print(e)
    sys.exit(1)

with conn, conn.cursor() as cur:
    cur.execute("SHOW server_version")
    print("Connected. PostgreSQL", cur.fetchone()[0])

    # Since PostgreSQL 15, ordinary users can't create tables in "public" unless they
    # own the database (or are granted it) - Django's migrations need this.
    cur.execute("SELECT has_schema_privilege('public', 'CREATE')")
    can_create = cur.fetchone()[0]
    # Django's test runner creates a temporary "test_washo" database, so it needs CREATEDB.
    cur.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user")
    can_createdb = cur.fetchone()[0]

print("Can create tables in schema public:", "YES" if can_create else "NO")
print("Can create databases (for tests):  ", "YES" if can_createdb else "NO")
sys.exit(0 if (can_create and can_createdb) else 2)

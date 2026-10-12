"""Additive schema changes for databases created by an earlier release.

create_all adds new tables but never new columns, so each column added to an existing table is listed here once, as
idempotent Postgres DDL. The bootstrap runs these under its advisory lock. SQLite (tests, local) builds fresh tables.
"""
from sqlalchemy import text
from sqlalchemy.engine import Connection

POSTGRES_MIGRATIONS: list[tuple[str, str, str]] = [
    ("instruction", "to_fund_code",
     "ALTER TABLE instruction ADD COLUMN IF NOT EXISTS to_fund_code VARCHAR(16) REFERENCES fund(code)"),
    ("instruction", "acknowledged_risk",
     "ALTER TABLE instruction ADD COLUMN IF NOT EXISTS acknowledged_risk BOOLEAN NOT NULL DEFAULT FALSE"),
]


def apply_migrations(connection: Connection) -> int:
    if connection.dialect.name != "postgresql":
        return 0
    for _, _, ddl in POSTGRES_MIGRATIONS:
        connection.execute(text(ddl))
    return len(POSTGRES_MIGRATIONS)

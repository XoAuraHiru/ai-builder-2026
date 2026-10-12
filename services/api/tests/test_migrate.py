import app.models  # noqa: F401  registers every table
from app.db import Base
from app.seed.migrate import POSTGRES_MIGRATIONS, apply_migrations


def test_every_migrated_column_exists_in_the_models():
    for table, column, ddl in POSTGRES_MIGRATIONS:
        assert column in Base.metadata.tables[table].columns, (table, column)
        assert table in ddl and column in ddl and "IF NOT EXISTS" in ddl


def test_migrations_only_run_on_postgres(db):
    assert apply_migrations(db.connection()) == 0

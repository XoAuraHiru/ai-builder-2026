from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.config import get_settings


def test_startup_survives_a_seed_that_collides_with_another_instance(db, monkeypatch):
    """Two Cloud Run instances seeding an empty database: the loser must still boot and serve."""
    import app.seed.generate as gen
    from app.main import app

    def collide(db, settings, **kwargs):
        raise IntegrityError("INSERT INTO person ...", {}, Exception("duplicate key value violates unique constraint"))

    monkeypatch.setattr(get_settings(), "auto_seed", True)
    monkeypatch.setattr(gen, "generate", collide)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200


def test_bootstrap_seeds_once_then_skips(db, monkeypatch):
    from app.seed.bootstrap import bootstrap_database

    monkeypatch.setattr(get_settings(), "auto_seed", True)
    assert bootstrap_database(get_settings()) == "seeded"
    assert bootstrap_database(get_settings()) == "skipped"
    monkeypatch.setattr(get_settings(), "auto_seed", False)
    assert bootstrap_database(get_settings()) == "disabled"


def test_cold_start_on_seeded_database_does_not_load_market_data_stack(tmp_path):
    """Scale-to-zero means every first visit is a cold start; an already-seeded database must not pay for yfinance."""
    import os
    import subprocess
    import sys

    db_url = f"sqlite+pysqlite:///{(tmp_path / 'cold.db').as_posix()}"
    script = (
        "import sys\n"
        "from app.db import SessionLocal, init_db\n"
        "from app.models import Person\n"
        "init_db()\n"
        "with SessionLocal() as db:\n"
        "    db.add(Person(kind='investor', full_name='Seeded', email='seeded@example.test'))\n"
        "    db.commit()\n"
        "from app.config import get_settings\n"
        "from app.seed.bootstrap import bootstrap_database\n"
        "print(bootstrap_database(get_settings()))\n"
        "print('yfinance' in sys.modules, 'app.seed.generate' in sys.modules)\n"
    )
    env = {**os.environ, "DATABASE_URL": db_url, "AUTO_SEED": "true", "MARKET_DATA_PROVIDER": "yfinance"}
    out = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["skipped", "False", "False"]

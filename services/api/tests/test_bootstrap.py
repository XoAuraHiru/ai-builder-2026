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

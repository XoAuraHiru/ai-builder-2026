from sqlalchemy import text

from app.config import Settings, get_settings
from app.db import SessionLocal, engine, init_db


def test_settings_defaults_pin_models_and_region():
    s = Settings(_env_file=None)
    assert s.gemini_flash_model == "gemini-3.8-flash"
    assert s.gemini_pro_model == "gemini-3.1-pro-preview"
    assert s.gcp_location == "us-central1"
    assert s.alpaca_paper is True


def test_get_settings_reads_test_environment():
    s = get_settings()
    assert s.auth_mode == "dev"
    assert s.database_url.startswith("sqlite")


def test_init_db_and_session_round_trip():
    init_db()
    with SessionLocal() as db:
        assert db.execute(text("select 1")).scalar() == 1
    assert engine.url.get_backend_name() == "sqlite"

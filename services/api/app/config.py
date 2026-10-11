from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Values come from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "local"                      # local | dev | prod
    database_url: str = "sqlite+pysqlite:///./atrium.db"
    auth_mode: str = "dev"                  # dev | firebase
    cors_origins: str = "http://localhost:3000"  # comma-separated list of allowed browser origins

    gcp_project: str = ""
    gcp_location: str = "us-central1"
    gemini_flash_model: str = "gemini-3.8-flash"
    gemini_pro_model: str = "gemini-3.1-pro-preview"

    market_data_provider: str = "fake"      # fake | yfinance | alpaca
    market_cache_dir: str = "data/cache"
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True

    pubsub_enabled: bool = False
    pubsub_topic: str = "atrium-events"

    auto_seed: bool = False                 # seed synthetic data at startup if the DB is empty
    seed: int = 42


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from typing import Literal

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
    gemini_location: str = "global"         # Gemini 3.x serve from the global endpoint (3.1 Pro preview is global-only)
    llm_provider: str = "fake"              # fake (offline, deterministic) | gemini
    gemini_flash_input_usd_per_m: float = 0.75   # Vertex AI list price, global endpoint, Oct 2026
    gemini_flash_output_usd_per_m: float = 3.75
    gemini_pro_input_usd_per_m: float = 2.0
    gemini_pro_output_usd_per_m: float = 12.0
    docai_location: str = "us"
    docai_proofing_processor: str = ""      # Document AI ID Proofing processor id; empty disables fraud signals
    docai_statement_processor: str = ""     # Document AI Bank Statement Parser id; empty means CSV statements only
    sample_statement_format: Literal["csv", "pdf"] = "csv"  # "pdf" reads the sample through Document AI, $0.75 a read
    blind_index_key: str = "atrium-local-blind-index-key"  # HMAC key for blind indexes; Secret Manager in production
    fund_search_engine: str = ""            # Vertex AI Search app id for fund documents; empty uses the local index
    fund_search_location: str = "global"
    lead_capture_limit_per_hour: int = 20   # per device and per IP hash, checked before any AI call
    lead_capture_global_per_hour: int = 60  # all public submissions together: caps AI spend if identifiers are forged

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

import os

import pytest

# Test environment is fixed before any app module is imported.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("AUTH_MODE", "dev")
os.environ.setdefault("MARKET_DATA_PROVIDER", "fake")
os.environ.setdefault("PUBSUB_ENABLED", "false")
os.environ["AUTO_SEED"] = "false"  # never seed test databases, even if a local .env says otherwise

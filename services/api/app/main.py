from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import init_db
from app.routers import accounts, funds, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = get_settings()
    if settings.auto_seed:
        from app.db import SessionLocal
        from app.seed.generate import generate, is_seeded

        with SessionLocal() as db:
            if not is_seeded(db):
                generate(db, settings)
                db.commit()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Atrium API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router)
    app.include_router(funds.router)
    app.include_router(accounts.router)
    return app


app = create_app()

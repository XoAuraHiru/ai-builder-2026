from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.routers import accounts, funds, health, me


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
    from app.events import get_event_bus, set_event_bus

    set_event_bus(get_event_bus(settings))
    app = FastAPI(title="Atrium API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(funds.router)
    app.include_router(accounts.router)
    app.include_router(me.router)
    return app


app = create_app()

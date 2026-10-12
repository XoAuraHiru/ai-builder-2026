from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import (accounts, ai, compliance, copilot, funds, health, insights, instructions, invest, leads,
                         markets, me, operations, profile, trading)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.seed.bootstrap import bootstrap_database

    app.state.bootstrap = bootstrap_database(get_settings())
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
    for module in (health, funds, accounts, me, leads, ai, invest, profile, insights, instructions, copilot, markets,
                   trading, operations, compliance):
        app.include_router(module.router)
    app.include_router(trading.staff_router)
    return app


app = create_app()

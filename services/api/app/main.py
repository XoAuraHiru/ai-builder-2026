from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import init_db
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Atrium API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router)
    return app


app = create_app()

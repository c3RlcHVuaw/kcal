from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kcal_tracker.api.routes import router
from kcal_tracker.config import validate_production_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    validate_production_settings()
    yield


app = FastAPI(title="Kcal Tracker API", version="0.1.0", lifespan=lifespan)
app.include_router(router)

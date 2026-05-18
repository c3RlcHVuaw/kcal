from __future__ import annotations

from fastapi import FastAPI

from kcal_tracker.api.routes import router

app = FastAPI(title="Kcal Tracker API", version="0.1.0")
app.include_router(router)


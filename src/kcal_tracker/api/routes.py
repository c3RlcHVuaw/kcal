from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.database import get_session
from kcal_tracker.schemas import (
    ActivityEstimate,
    AIUsageSummary,
    AppleHealthImport,
    AppleHealthImportResult,
    DiarySummary,
    FoodEntryCreate,
    FoodEntryRead,
    UserRead,
)
from kcal_tracker.services.ai_usage import AIUsageService
from kcal_tracker.services.diary import DiaryService
from kcal_tracker.services.users import UserService
from kcal_tracker.services.wellness import WellnessService

router = APIRouter()
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@router.post("/users/{telegram_id}", response_model=UserRead)
async def upsert_user(
    telegram_id: int,
    session: SessionDep,
    username: str | None = None,
) -> UserRead:
    return await UserService(session).get_or_create(telegram_id=telegram_id, username=username)


@router.get("/users/{telegram_id}/diary/today", response_model=DiarySummary)
async def today_diary(
    telegram_id: int,
    session: SessionDep,
) -> DiarySummary:
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return await DiaryService(session).today_summary(user)


@router.get("/users/{telegram_id}/ai-usage/today", response_model=AIUsageSummary)
async def today_ai_usage(
    telegram_id: int,
    session: SessionDep,
) -> AIUsageSummary:
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    usage_service = AIUsageService(session)
    used_today = await usage_service.today_count(user)
    return AIUsageSummary(
        used_today=used_today,
        remaining_today=max(settings.ai_daily_request_limit - used_today, 0),
        daily_limit=settings.ai_daily_request_limit,
    )


@router.post("/users/{telegram_id}/entries", response_model=FoodEntryRead)
async def create_entry(
    telegram_id: int,
    payload: FoodEntryCreate,
    session: SessionDep,
) -> FoodEntryRead:
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return await DiaryService(session).add_entry(user, payload)


@router.post("/integrations/apple-health/{token}", response_model=AppleHealthImportResult)
async def import_apple_health(
    token: str,
    payload: AppleHealthImport,
    session: SessionDep,
) -> AppleHealthImportResult:
    user = await UserService(session).get_by_apple_health_token(token)
    if user is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    saved: list[str] = []
    wellness = WellnessService(session)
    if payload.weight_kg is not None:
        await wellness.add_weight(user, payload.weight_kg)
        saved.append("weight")
    if payload.active_kcal is not None and payload.active_kcal > 0:
        await wellness.add_activity(
            user,
            ActivityEstimate(
                name=payload.note or "Apple Health active energy",
                kcal=payload.active_kcal,
                confidence=None,
            ),
            "apple_health",
        )
        saved.append("active_kcal")
    elif payload.steps is not None and payload.steps > 0:
        kcal = _steps_to_kcal(payload.steps)
        if kcal > 0:
            await wellness.add_activity(
                user,
                ActivityEstimate(
                    name=f"Apple Health steps: {payload.steps}",
                    kcal=kcal,
                    confidence=None,
                ),
                "apple_health",
            )
            saved.append("steps")

    if not saved:
        raise HTTPException(status_code=400, detail="Nothing to import")
    return AppleHealthImportResult(ok=True, saved=saved)


def _steps_to_kcal(steps: int) -> float:
    return round(steps * 0.04, 1)

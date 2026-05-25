from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.database import engine, get_session
from kcal_tracker.schemas import (
    ActivityEstimate,
    ActivityLogRead,
    AIUsageSummary,
    AnalyticsDay,
    AppleHealthImportResult,
    DiarySummary,
    FoodEntryCreate,
    FoodEntryRead,
    UserRead,
    WebAppBodySummary,
    WebAppFavoriteFood,
    WebAppFrequentFood,
    WebAppHabitSummary,
    WebAppToday,
    WebAppWaterCreate,
    WebAppWeightCreate,
    WebAppWeightPoint,
    WeeklyAnalyticsRead,
    WeightGoalRead,
    WeightGoalUpdate,
)
from kcal_tracker.services.ai_usage import AIUsageService
from kcal_tracker.services.diary import DiaryService
from kcal_tracker.services.export import ExportService
from kcal_tracker.services.profile import (
    apply_default_macro_targets,
    calculate_daily_kcal_target,
    weight_goal_summary,
)
from kcal_tracker.services.subscriptions import user_ai_daily_limit
from kcal_tracker.services.users import UserService
from kcal_tracker.services.webapp_auth import (
    WebAppAuthError,
    WebAppIdentity,
    validate_webapp_init_data,
)
from kcal_tracker.services.wellness import WellnessService

logger = logging.getLogger(__name__)
router = APIRouter()
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_webapp_identity(request: Request) -> WebAppIdentity:
    init_data = request.headers.get("x-telegram-init-data", "")
    try:
        return validate_webapp_init_data(init_data)
    except WebAppAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


WebAppIdentityDep = Annotated[WebAppIdentity, Depends(get_webapp_identity)]


@router.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    checks = {
        "database": await _check_database(),
        "redis": await _check_redis(),
    }
    ok = all(checks.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"ok": ok, "checks": checks},
    )


@router.get("/payments/yookassa/return")
async def yookassa_return() -> dict[str, str]:
    return {"status": "ok", "message": "Вернитесь в Telegram: бот проверит оплату автоматически."}


@router.post("/users/{telegram_id}", response_model=UserRead)
async def upsert_user(
    telegram_id: int,
    session: SessionDep,
    username: str | None = None,
) -> UserRead:
    return await UserService(session).get_or_create(telegram_id=telegram_id, username=username)


@router.get("/users/{telegram_id}", response_model=UserRead)
async def get_user(
    telegram_id: int,
    session: SessionDep,
) -> UserRead:
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/{telegram_id}/diary/today", response_model=DiarySummary)
async def today_diary(
    telegram_id: int,
    session: SessionDep,
) -> DiarySummary:
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return await DiaryService(session).today_summary(user)


@router.get("/users/{telegram_id}/analytics/week", response_model=WeeklyAnalyticsRead)
async def week_analytics(
    telegram_id: int,
    session: SessionDep,
) -> WeeklyAnalyticsRead:
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    analytics = await DiaryService(session).weekly_analytics(user)
    return WeeklyAnalyticsRead(
        days=[
            AnalyticsDay(
                date=day.date_label,
                kcal=day.kcal,
                protein=day.protein,
                fat=day.fat,
                carbs=day.carbs,
                entries_count=day.entries_count,
            )
            for day in analytics.days
        ],
        average_kcal=analytics.average_kcal,
        target_kcal=analytics.target_kcal,
        days_in_target=analytics.days_in_target,
    )


@router.get("/users/{telegram_id}/goals/weight", response_model=WeightGoalRead)
async def get_weight_goal(
    telegram_id: int,
    session: SessionDep,
) -> WeightGoalRead:
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return weight_goal_summary(user)


@router.put("/users/{telegram_id}/goals/weight", response_model=WeightGoalRead)
async def update_weight_goal(
    telegram_id: int,
    payload: WeightGoalUpdate,
    session: SessionDep,
) -> WeightGoalRead:
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.goal = payload.goal
    user.target_weight_kg = payload.target_weight_kg
    user.weekly_weight_change_kg = payload.weekly_weight_change_kg
    user.daily_kcal_target = calculate_daily_kcal_target(user)
    apply_default_macro_targets(user)
    await session.commit()
    await session.refresh(user)
    return weight_goal_summary(user)


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
    daily_limit = user_ai_daily_limit(user)
    return AIUsageSummary(
        used_today=used_today,
        remaining_today=10**9 if daily_limit is None else max(daily_limit - used_today, 0),
        daily_limit=0 if daily_limit is None else daily_limit,
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


@router.get("/users/{telegram_id}/exports/food.csv")
async def export_food_csv(
    telegram_id: int,
    session: SessionDep,
) -> PlainTextResponse:
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    csv = await ExportService(session).food_csv(user)
    return PlainTextResponse(
        csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kcal_food.csv"'},
    )


@router.get("/users/{telegram_id}/exports/wellness.csv")
async def export_wellness_csv(
    telegram_id: int,
    session: SessionDep,
) -> PlainTextResponse:
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    csv = await ExportService(session).wellness_csv(user)
    return PlainTextResponse(
        csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kcal_wellness.csv"'},
    )


@router.get("/webapp/me/today", response_model=WebAppToday)
async def webapp_today(
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> WebAppToday:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    diary = await DiaryService(session).today_summary(user)
    wellness = WellnessService(session)
    latest_weight = await wellness.latest_weight(user)
    usage_service = AIUsageService(session)
    used_today = await usage_service.today_count(user)
    daily_limit = user_ai_daily_limit(user)
    return WebAppToday(
        user=user,
        diary=diary,
        water_ml=await wellness.today_water_ml(user),
        latest_weight_kg=latest_weight.weight_kg if latest_weight else user.weight,
        ai_usage=AIUsageSummary(
            used_today=used_today,
            remaining_today=10**9 if daily_limit is None else max(daily_limit - used_today, 0),
            daily_limit=0 if daily_limit is None else daily_limit,
        ),
        weight_goal=weight_goal_summary(user),
    )


@router.post("/webapp/me/entries", response_model=FoodEntryRead)
async def webapp_create_entry(
    payload: FoodEntryCreate,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> FoodEntryRead:
    if payload.source != "manual":
        raise HTTPException(status_code=400, detail="Web app supports manual entries only")
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    return await DiaryService(session).add_entry(user, payload)


@router.post("/webapp/me/water")
async def webapp_add_water(
    payload: WebAppWaterCreate,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> dict[str, int]:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    wellness = WellnessService(session)
    await wellness.add_water(user, payload.amount_ml)
    return {"water_ml": await wellness.today_water_ml(user)}


@router.post("/webapp/me/weight")
async def webapp_add_weight(
    payload: WebAppWeightCreate,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> dict[str, float]:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    log = await WellnessService(session).add_weight(user, payload.weight_kg)
    return {"weight_kg": log.weight_kg}


@router.get("/webapp/me/week", response_model=WeeklyAnalyticsRead)
async def webapp_week(
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> WeeklyAnalyticsRead:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    analytics = await DiaryService(session).weekly_analytics(user)
    return WeeklyAnalyticsRead(
        days=[
            AnalyticsDay(
                date=day.date_label,
                kcal=day.kcal,
                protein=day.protein,
                fat=day.fat,
                carbs=day.carbs,
                entries_count=day.entries_count,
            )
            for day in analytics.days
        ],
        average_kcal=analytics.average_kcal,
        target_kcal=analytics.target_kcal,
        days_in_target=analytics.days_in_target,
    )


@router.get("/webapp/me/body", response_model=WebAppBodySummary)
async def webapp_body(
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> WebAppBodySummary:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    wellness = WellnessService(session)
    trend = await wellness.weight_trend(user)
    habits = await wellness.habit_summary(user)
    return WebAppBodySummary(
        latest_weight_kg=trend.latest_kg,
        average_7d_kg=trend.average_7d_kg,
        delta_7d_kg=trend.delta_7d_kg,
        trend_label=trend.trend_label,
        weight_logs=[
            WebAppWeightPoint(
                date=log.created_at.strftime("%d.%m"),
                weight_kg=log.weight_kg,
            )
            for log in trend.logs[-14:]
        ],
        habit_summary=WebAppHabitSummary(
            food_streak_days=habits.food_streak_days,
            water_streak_days=habits.water_streak_days,
            weight_streak_days=habits.weight_streak_days,
            tracked_food_days_30=habits.tracked_food_days_30,
            tracked_water_days_30=habits.tracked_water_days_30,
            tracked_weight_days_30=habits.tracked_weight_days_30,
            best_habit=habits.best_habit,
        ),
    )


@router.put("/webapp/me/goals/weight", response_model=WeightGoalRead)
async def webapp_update_weight_goal(
    payload: WeightGoalUpdate,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> WeightGoalRead:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    user.goal = payload.goal
    user.target_weight_kg = payload.target_weight_kg
    user.weekly_weight_change_kg = payload.weekly_weight_change_kg
    user.daily_kcal_target = calculate_daily_kcal_target(user)
    apply_default_macro_targets(user)
    await session.commit()
    await session.refresh(user)
    return weight_goal_summary(user)


@router.get("/webapp/me/frequent", response_model=list[WebAppFrequentFood])
async def webapp_frequent_foods(
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> list[WebAppFrequentFood]:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    frequent = await DiaryService(session).frequent_foods(user)
    return [
        WebAppFrequentFood(
            entry=FoodEntryRead.model_validate(item.entry),
            count=item.count,
        )
        for item in frequent
    ]


@router.post("/webapp/me/repeat-entry/{entry_id}", response_model=FoodEntryRead)
async def webapp_repeat_entry(
    entry_id: int,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> FoodEntryRead:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    entry = await DiaryService(session).repeat_entry(user, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return FoodEntryRead.model_validate(entry)


@router.post("/webapp/me/repeat-yesterday", response_model=list[FoodEntryRead])
async def webapp_repeat_yesterday(
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> list[FoodEntryRead]:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    entries = await DiaryService(session).repeat_yesterday(user)
    return [FoodEntryRead.model_validate(entry) for entry in entries]


@router.delete("/webapp/me/entries/latest")
async def webapp_delete_latest_entry(
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> dict[str, bool]:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    deleted = await DiaryService(session).delete_latest_entry(user)
    return {"deleted": deleted is not None}


@router.delete("/webapp/me/entries/{entry_id}")
async def webapp_delete_entry(
    entry_id: int,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> dict[str, bool]:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    deleted = await DiaryService(session).delete_entry(user, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"deleted": True}


@router.post("/webapp/me/entries/{entry_id}/favorite", response_model=WebAppFavoriteFood)
async def webapp_favorite_entry(
    entry_id: int,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> WebAppFavoriteFood:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    diary = DiaryService(session)
    entry = await diary.get_entry(user, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    favorite = await WellnessService(session).add_favorite_from_entry(user, entry)
    return _favorite_read(favorite)


@router.get("/webapp/me/favorites", response_model=list[WebAppFavoriteFood])
async def webapp_favorites(
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> list[WebAppFavoriteFood]:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    favorites = await WellnessService(session).favorites(user)
    return [_favorite_read(favorite) for favorite in favorites]


@router.post("/webapp/me/favorites/{favorite_id}", response_model=FoodEntryRead)
async def webapp_add_favorite_to_diary(
    favorite_id: int,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> FoodEntryRead:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    wellness = WellnessService(session)
    favorite = await wellness.favorite(user, favorite_id)
    if favorite is None:
        raise HTTPException(status_code=404, detail="Favorite not found")
    entry = await DiaryService(session).add_entry(user, wellness.favorite_payload(favorite))
    return FoodEntryRead.model_validate(entry)


@router.post("/webapp/me/activity", response_model=ActivityLogRead)
async def webapp_add_activity(
    payload: ActivityEstimate,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> ActivityLogRead:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    activity = await WellnessService(session).add_activity(user, payload, "manual")
    return _activity_read(activity)


@router.get("/webapp/me/activity/today", response_model=list[ActivityLogRead])
async def webapp_today_activities(
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> list[ActivityLogRead]:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    activities = await WellnessService(session).today_activities(user)
    return [_activity_read(activity) for activity in activities]


@router.delete("/webapp/me/activity/{activity_id}")
async def webapp_delete_activity(
    activity_id: int,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> dict[str, bool]:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    deleted = await WellnessService(session).delete_activity(user, activity_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return {"deleted": True}


@router.get("/webapp/me/exports/food.csv")
async def webapp_export_food_csv(
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> PlainTextResponse:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    csv = await ExportService(session).food_csv(user)
    return PlainTextResponse(
        csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kcal_food.csv"'},
    )


@router.post("/integrations/apple-health/{token}", response_model=AppleHealthImportResult)
async def import_apple_health(
    token: str,
    request: Request,
    session: SessionDep,
) -> AppleHealthImportResult:
    user = await UserService(session).get_by_apple_health_token(token)
    if user is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    raw_payload = await _read_apple_health_payload(request)
    logger.info(
        "Apple Health payload received user_id=%s summary=%s",
        user.id,
        _apple_health_payload_summary(raw_payload),
    )
    payload, errors = _normalize_apple_health_payload(raw_payload)

    saved: list[str] = []
    wellness = WellnessService(session)
    if payload.weight_kg is not None:
        await wellness.add_weight(user, payload.weight_kg)
        saved.append("weight")
    if payload.active_kcal is not None and payload.active_kcal > 0:
        delta = await wellness.apple_health_delta(user, "active_kcal", payload.active_kcal)
        if delta > 0:
            await wellness.add_activity(
                user,
                ActivityEstimate(
                    name=payload.note or "Apple Health active energy",
                    kcal=delta,
                    confidence=None,
                ),
                "apple_health",
            )
            saved.append("active_kcal")
    elif payload.steps is not None and payload.steps > 0:
        step_delta = await wellness.apple_health_delta(user, "steps", payload.steps)
        kcal_delta = _steps_to_kcal(int(step_delta))
        if kcal_delta > 0:
            await wellness.add_activity(
                user,
                ActivityEstimate(
                    name=f"Apple Health steps: {payload.steps}",
                    kcal=kcal_delta,
                    confidence=None,
                ),
                "apple_health",
            )
            saved.append("steps")

    if not saved:
        if payload.has_values:
            return AppleHealthImportResult(ok=True, saved=saved)
        detail: dict[str, Any] = {"message": "Nothing to import"}
        if errors:
            detail["errors"] = errors
        raise HTTPException(status_code=400, detail=detail)
    return AppleHealthImportResult(ok=True, saved=saved)


def _activity_read(activity) -> ActivityLogRead:
    return ActivityLogRead(
        id=activity.id,
        name=activity.activity_name,
        kcal=activity.kcal,
        confidence=activity.confidence,
        source=activity.source,
        created_at=activity.created_at,
    )


def _favorite_read(favorite) -> WebAppFavoriteFood:
    return WebAppFavoriteFood(
        id=favorite.id,
        name=favorite.food_name,
        kcal=favorite.kcal,
        protein=favorite.protein,
        fat=favorite.fat,
        carbs=favorite.carbs,
        weight_g=favorite.weight_g,
        emoji=favorite.emoji,
        advice=favorite.advice,
        created_at=favorite.created_at,
    )


async def _check_database() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
    except Exception:
        logger.exception("Readiness database check failed")
        return False
    return True


async def _check_redis() -> bool:
    redis = Redis.from_url(settings.redis_url)
    try:
        return bool(await redis.ping())
    except Exception:
        logger.exception("Readiness Redis check failed")
        return False
    finally:
        await redis.aclose()


async def _read_apple_health_payload(request: Request) -> dict[str, Any]:
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail={"message": "Empty request body"})
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid JSON body", "error": str(exc)},
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail={"message": "JSON body must be an object"},
        )
    return payload


def _normalize_apple_health_payload(
    payload: dict[str, Any],
) -> tuple[AppleHealthPayload, dict[str, str]]:
    errors: dict[str, str] = {}
    weight_kg = _extract_float_field(payload, "weight_kg", 30, 250, errors)
    steps_float = _extract_float_field(payload, "steps", 0, 100000, errors, sum_samples=True)
    active_kcal = _extract_float_field(
        payload,
        "active_kcal",
        0,
        5000,
        errors,
        sum_samples=True,
    )
    note = payload.get("note")
    if note is not None and not isinstance(note, str):
        note = str(note)
    if isinstance(note, str):
        note = note[:255]
    steps = int(round(steps_float)) if steps_float is not None else None
    return AppleHealthPayload(weight_kg, steps, active_kcal, note), errors


def _apple_health_payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    known_fields = ("weight_kg", "steps", "active_kcal", "note")
    present_fields = [field for field in known_fields if field in payload]
    return {
        "fields": present_fields,
        "extra_field_count": max(len(payload) - len(present_fields), 0),
    }


def _extract_float_field(
    payload: dict[str, Any],
    field: str,
    minimum: float,
    maximum: float,
    errors: dict[str, str],
    *,
    sum_samples: bool = False,
) -> float | None:
    if field not in payload:
        return None
    if sum_samples:
        value = _extract_numeric_total(payload[field])
    else:
        value = _extract_numeric_value(payload[field])
    if value is None:
        errors[field] = "Could not extract numeric value"
        return None
    if not minimum <= value <= maximum:
        errors[field] = f"Value must be between {minimum:g} and {maximum:g}"
        return None
    return value


def _extract_numeric_value(input_value: Any) -> float | None:
    if isinstance(input_value, bool):
        return None
    if isinstance(input_value, int | float):
        return float(input_value)
    if isinstance(input_value, str):
        return _number_from_string(input_value)
    if isinstance(input_value, list):
        for item in input_value:
            value = _extract_numeric_value(item)
            if value is not None:
                return value
        return None
    if isinstance(input_value, dict):
        priority_keys = (
            "quantity",
            "sumQuantity",
            "total",
            "totalQuantity",
            "doubleValue",
            "floatValue",
            "intValue",
            "numericValue",
            "value",
            "sample",
            "samples",
            "result",
            "results",
        )
        for key in priority_keys:
            if key in input_value:
                value = _extract_numeric_value(input_value[key])
                if value is not None:
                    return value
        for key, nested_value in input_value.items():
            if key in priority_keys:
                continue
            value = _extract_numeric_value(nested_value)
            if value is not None:
                return value
    return None


def _extract_numeric_total(input_value: Any) -> float | None:
    if isinstance(input_value, str):
        return _number_total_from_string(input_value)
    if isinstance(input_value, list):
        values = [_extract_numeric_value(item) for item in input_value]
        numeric_values = [value for value in values if value is not None]
        return sum(numeric_values) if numeric_values else None
    if isinstance(input_value, dict):
        for key in ("samples", "result", "results"):
            nested = input_value.get(key)
            if isinstance(nested, list):
                return _extract_numeric_total(nested)
        return _extract_numeric_value(input_value)
    return _extract_numeric_value(input_value)


def _number_total_from_string(value: str) -> float | None:
    stripped = value.strip().replace(",", ".")
    if not stripped:
        return None
    matches = re.findall(r"-?\d+(?:\.\d+)?", stripped)
    if not matches:
        return None
    return sum(float(match) for match in matches)


def _single_number_from_string(value: str) -> float | None:
    stripped = value.strip().replace(",", ".")
    if not stripped:
        return None
    matches = re.findall(r"-?\d+(?:\.\d+)?", stripped)
    if len(matches) != 1:
        return None
    return float(matches[0])


def _number_from_string(value: str) -> float | None:
    stripped = value.strip().replace(",", ".")
    try:
        return float(stripped)
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?", stripped)
        if match is None:
            return None
        try:
            return float(match.group())
        except ValueError:
            return None


@dataclass(frozen=True)
class AppleHealthPayload:
    weight_kg: float | None
    steps: int | None
    active_kcal: float | None
    note: str | None

    @property
    def has_values(self) -> bool:
        return (
            self.weight_kg is not None
            or self.steps is not None
            or self.active_kcal is not None
        )


def _steps_to_kcal(steps: int) -> float:
    return round(steps * 0.04, 1)

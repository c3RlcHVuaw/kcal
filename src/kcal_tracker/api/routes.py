from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.database import get_session
from kcal_tracker.schemas import (
    ActivityEstimate,
    AIUsageSummary,
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

logger = logging.getLogger(__name__)
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
    request: Request,
    session: SessionDep,
) -> AppleHealthImportResult:
    user = await UserService(session).get_by_apple_health_token(token)
    if user is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    raw_payload = await _read_apple_health_payload(request)
    logger.warning("Apple Health raw payload for user_id=%s: %s", user.id, raw_payload)
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

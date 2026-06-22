from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

from kcal_tracker.config import settings
from kcal_tracker.services.throttle import ThrottleLimitReached, ensure_rate_limit


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


async def read_apple_health_payload(request: Request) -> dict[str, Any]:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.apple_health_payload_max_bytes:
                raise HTTPException(status_code=413, detail={"message": "Request body is too large"})
        except ValueError:
            pass

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail={"message": "Empty request body"})
    if len(body) > settings.apple_health_payload_max_bytes:
        raise HTTPException(status_code=413, detail={"message": "Request body is too large"})
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


async def ensure_apple_health_import_allowed(token: str, request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:24]
    try:
        await ensure_rate_limit(
            f"apple-health:ip:{client_host}",
            limit=settings.apple_health_import_rate_limit_per_minute,
            window_seconds=60,
        )
        await ensure_rate_limit(
            f"apple-health:token:{token_hash}",
            limit=settings.apple_health_import_rate_limit_per_minute,
            window_seconds=60,
        )
    except ThrottleLimitReached as exc:
        raise HTTPException(
            status_code=429,
            detail="Too many Apple Health imports",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


def normalize_apple_health_payload(
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


def apple_health_payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
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
        value = extract_numeric_total(payload[field])
    else:
        value = extract_numeric_value(payload[field])
    if value is None:
        errors[field] = "Could not extract numeric value"
        return None
    if not minimum <= value <= maximum:
        errors[field] = f"Value must be between {minimum:g} and {maximum:g}"
        return None
    return value


def extract_numeric_value(input_value: Any) -> float | None:
    if isinstance(input_value, bool):
        return None
    if isinstance(input_value, int | float):
        return float(input_value)
    if isinstance(input_value, str):
        return _number_from_string(input_value)
    if isinstance(input_value, list):
        for item in input_value:
            value = extract_numeric_value(item)
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
                value = extract_numeric_value(input_value[key])
                if value is not None:
                    return value
        for key, nested_value in input_value.items():
            if key in priority_keys:
                continue
            value = extract_numeric_value(nested_value)
            if value is not None:
                return value
    return None


def extract_numeric_total(input_value: Any) -> float | None:
    if isinstance(input_value, str):
        return _number_total_from_string(input_value)
    if isinstance(input_value, list):
        values = [extract_numeric_value(item) for item in input_value]
        numeric_values = [value for value in values if value is not None]
        return sum(numeric_values) if numeric_values else None
    if isinstance(input_value, dict):
        for key in ("samples", "result", "results"):
            nested = input_value.get(key)
            if isinstance(nested, list):
                return extract_numeric_total(nested)
        return extract_numeric_value(input_value)
    return extract_numeric_value(input_value)


def _number_total_from_string(value: str) -> float | None:
    stripped = value.strip().replace(",", ".")
    if not stripped:
        return None
    matches = re.findall(r"-?\d+(?:\.\d+)?", stripped)
    if not matches:
        return None
    return sum(float(match) for match in matches)


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


def steps_to_kcal(steps: int) -> float:
    return round(steps * 0.04, 1)

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FoodEstimate(BaseModel):
    name: str
    weight_g: float | None = Field(default=None, ge=0)
    kcal: float = Field(ge=0)
    protein: float = Field(default=0, ge=0)
    fat: float = Field(default=0, ge=0)
    carbs: float = Field(default=0, ge=0)
    confidence: float | None = Field(default=None, ge=0, lt=1)
    emoji: str | None = Field(default=None, max_length=16)
    advice: str | None = Field(default=None, max_length=255)


class FoodEstimateList(BaseModel):
    foods: list[FoodEstimate]


class FoodEntryCreate(FoodEstimate):
    source: str = Field(pattern="^(ai_photo|manual|food_search|barcode|apple_health)$")


class FoodEntryRead(FoodEntryCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityEstimate(BaseModel):
    name: str
    kcal: float = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, lt=1)


class AppleHealthImport(BaseModel):
    weight_kg: float | None = Field(default=None, ge=30, le=250)
    steps: int | None = Field(default=None, ge=0, le=100000)
    active_kcal: float | None = Field(default=None, ge=0, le=5000)
    note: str | None = Field(default=None, max_length=255)


class AppleHealthImportResult(BaseModel):
    ok: bool
    saved: list[str]


class DiarySummary(BaseModel):
    kcal: float
    protein: float
    fat: float
    carbs: float
    activity_kcal: float = 0
    base_target_kcal: int
    target_kcal: int
    target_protein: float
    target_fat: float
    target_carbs: float
    entries: list[FoodEntryRead]


class UserRead(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    timezone: str
    daily_kcal_target: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AIUsageSummary(BaseModel):
    used_today: int
    remaining_today: int
    daily_limit: int

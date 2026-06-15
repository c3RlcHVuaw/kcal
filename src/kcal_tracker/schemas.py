from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, Field, model_validator


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
    source_label: str | None = Field(default=None, max_length=32)
    catalog_id: int | None = None
    is_ai_suggestion: bool = False
    trust_score: float | None = Field(default=None, ge=0, le=1)
    packaged: bool | None = None
    photo_thumb_data_url: str | None = Field(default=None, max_length=70000)
    photo_thumb_expires_at: datetime | None = None


class FoodEstimateList(BaseModel):
    foods: list[FoodEstimate]


class FoodEntryCreate(FoodEstimate):
    source: str = Field(pattern="^(ai_photo|manual|food_search|barcode|apple_health|history)$")
    meal_type: str | None = Field(
        default=None,
        pattern="^(breakfast|lunch|dinner|snack)$",
    )


class FoodEntryRead(FoodEntryCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def hide_expired_photo_thumb(self) -> FoodEntryRead:
        expires_at = self.photo_thumb_expires_at
        if expires_at is None:
            self.photo_thumb_data_url = None
            return self
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            self.photo_thumb_data_url = None
            self.photo_thumb_expires_at = None
        return self


class FoodEntryUpdate(FoodEstimate):
    meal_type: str | None = Field(
        default=None,
        pattern="^(breakfast|lunch|dinner|snack)$",
    )


class WebAppFoodTextParse(BaseModel):
    text: str = Field(min_length=3, max_length=500)


class WebAppBarcodeLookup(BaseModel):
    code: str = Field(min_length=8, max_length=64)


class WebAppFoodRefine(BaseModel):
    estimate: FoodEstimate
    text: str = Field(min_length=2, max_length=500)
    source: str = Field(default="ai", pattern="^(history|common|food_search|ai|photo|barcode)$")


class WebAppFoodTextParseResult(BaseModel):
    foods: list[FoodEstimate]
    source: str = Field(pattern="^(history|common|food_search|ai|photo|barcode)$")
    ai_used: bool = False
    remaining_ai_today: int | None = None
    barcode: str | None = None


class WebAppQualityEventCreate(BaseModel):
    event_type: str = Field(
        pattern=(
            "^(webapp_ai_accept|webapp_ai_reject|webapp_ai_adjust|webapp_ai_failed|"
            "webapp_first_food_saved|webapp_paywall_open|webapp_search_failed|"
            "webapp_barcode_failed|webapp_weekly_bonus_claim|webapp_brand_lookup)$"
        )
    )
    source: str | None = Field(default=None, max_length=64)
    query: str | None = Field(default=None, max_length=512)
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class LandingEventCreate(BaseModel):
    event_type: str = Field(pattern="^(view|bot_click)$")
    path: str = Field(default="/", max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    referrer: str | None = Field(default=None, max_length=512)
    utm_source: str | None = Field(default=None, max_length=128)
    utm_medium: str | None = Field(default=None, max_length=128)
    utm_campaign: str | None = Field(default=None, max_length=128)
    utm_content: str | None = Field(default=None, max_length=128)
    utm_term: str | None = Field(default=None, max_length=128)
    visitor_id: str | None = Field(default=None, max_length=64)
    session_id: str | None = Field(default=None, max_length=64)


class WebAppPromoValidate(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class WebAppPromoPlan(BaseModel):
    code: str
    title: str
    rub: int
    stars: int
    daily_limit: int | None = None


class WebAppPromoValidateResult(BaseModel):
    valid: bool
    code: str | None = None
    discount_percent: int | None = None
    plans: list[WebAppPromoPlan] = Field(default_factory=list)


class WebAppSubscriptionPlans(BaseModel):
    plans: list[WebAppPromoPlan]


class ActivityEstimate(BaseModel):
    name: str
    kcal: float = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, lt=1)


class ActivityLogRead(ActivityEstimate):
    id: int
    source: str
    created_at: datetime


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
    goal: str | None = None
    weight: float | None = None
    target_weight_kg: float | None = None
    weekly_weight_change_kg: float | None = None
    daily_kcal_target: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AIUsageSummary(BaseModel):
    used_today: int
    remaining_today: int
    daily_limit: int
    trial_used: int = 0
    trial_remaining: int | None = None
    trial_limit: int | None = None
    is_trial: bool = False


class WeightGoalUpdate(BaseModel):
    goal: str = Field(pattern="^(loss|maintain|gain)$")
    target_weight_kg: float | None = Field(default=None, ge=30, le=250)
    weekly_weight_change_kg: float | None = Field(default=None, ge=0.1, le=1.5)


class WebAppOnboardingComplete(BaseModel):
    goal: str = Field(pattern="^(loss|maintain|gain)$")
    gender: str = Field(pattern="^(male|female)$")
    age: int = Field(ge=13, le=100)
    height: float = Field(ge=100, le=240)
    weight: float = Field(ge=30, le=250)
    activity: str = Field(pattern="^(low|medium|high)$")
    target_weight_kg: float | None = Field(default=None, ge=30, le=250)
    weekly_weight_change_kg: float | None = Field(default=None, ge=0.1, le=1.5)


class WeightGoalRead(BaseModel):
    goal: str | None
    current_weight_kg: float | None
    target_weight_kg: float | None
    weekly_weight_change_kg: float | None
    daily_kcal_target: int
    forecast_weeks: int | None
    forecast_text: str


class AnalyticsDay(BaseModel):
    date: str
    kcal: float
    protein: float
    fat: float
    carbs: float
    entries_count: int


class WeeklyAnalyticsRead(BaseModel):
    days: list[AnalyticsDay]
    average_kcal: float
    target_kcal: int
    days_in_target: int


class WebAppUser(BaseModel):
    telegram_id: int
    username: str | None
    first_name: str | None = None


class WebAppWeeklyMission(BaseModel):
    key: str
    title: str
    current: int
    target: int
    completed: bool


class WebAppWeeklyMissions(BaseModel):
    week_start: date
    missions: list[WebAppWeeklyMission]
    completed_count: int
    eligible_for_bonus: bool = False
    bonus_claimed: bool = False


class WebAppToday(BaseModel):
    user: UserRead
    diary: DiarySummary
    water_ml: int
    latest_weight_kg: float | None
    ai_usage: AIUsageSummary
    onboarding_completed: bool = False
    has_active_subscription: bool = False
    subscription_plan: str | None = None
    subscription_expires_at: datetime | None = None
    subscription_days_left: int | None = None
    weight_goal: WeightGoalRead
    weekly_missions: WebAppWeeklyMissions | None = None


class WebAppWaterCreate(BaseModel):
    amount_ml: int = Field(ge=1, le=5000)


class WebAppWeightCreate(BaseModel):
    weight_kg: float = Field(ge=30, le=250)


class WebAppFrequentFood(BaseModel):
    entry: FoodEntryRead
    count: int


class WebAppFavoriteFood(BaseModel):
    id: int
    name: str
    kcal: float
    protein: float
    fat: float
    carbs: float
    weight_g: float | None = None
    emoji: str | None = None
    advice: str | None = None
    created_at: datetime


class WebAppWeightPoint(BaseModel):
    date: str
    weight_kg: float


class WebAppHabitSummary(BaseModel):
    food_streak_days: int
    water_streak_days: int
    weight_streak_days: int
    tracked_food_days_30: int
    tracked_water_days_30: int
    tracked_weight_days_30: int
    best_habit: str


class WebAppBodySummary(BaseModel):
    latest_weight_kg: float | None
    average_7d_kg: float | None
    delta_7d_kg: float | None
    trend_label: str
    weight_logs: list[WebAppWeightPoint]
    habit_summary: WebAppHabitSummary

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from PIL import Image, ImageOps
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
    FoodEntryUpdate,
    FoodEstimate,
    UserRead,
    WebAppBarcodeLookup,
    WebAppBodySummary,
    WebAppFavoriteFood,
    WebAppFoodRefine,
    WebAppFoodTextParse,
    WebAppFoodTextParseResult,
    WebAppFrequentFood,
    WebAppHabitSummary,
    WebAppOnboardingComplete,
    WebAppPromoPlan,
    WebAppPromoValidate,
    WebAppPromoValidateResult,
    WebAppQualityEventCreate,
    WebAppSubscriptionPlans,
    WebAppToday,
    WebAppWaterCreate,
    WebAppWeeklyMission,
    WebAppWeeklyMissions,
    WebAppWeightCreate,
    WebAppWeightPoint,
    WeeklyAnalyticsRead,
    WeightGoalRead,
    WeightGoalUpdate,
)
from kcal_tracker.services.ai_food import AIFoodService
from kcal_tracker.services.ai_usage import AILimitReachedError, AIUsageService
from kcal_tracker.services.barcode import BarcodeNotFoundError, BarcodeService, normalize_barcode
from kcal_tracker.services.diary import DiaryService, estimate_from_entry
from kcal_tracker.services.export import ExportService
from kcal_tracker.services.fatsecret import FatSecretService
from kcal_tracker.services.food_catalog import FoodCatalogService, mark_ai_suggestions
from kcal_tracker.services.food_insights import enrich_food_payload
from kcal_tracker.services.food_search import estimate_common_food
from kcal_tracker.services.growth import GrowthService
from kcal_tracker.services.open_food_facts import OpenFoodFactsService, ProductNotFoundError
from kcal_tracker.services.profile import (
    apply_default_macro_targets,
    calculate_daily_kcal_target,
    weight_goal_summary,
)
from kcal_tracker.services.quality import record_quality_event
from kcal_tracker.services.subscriptions import (
    SubscriptionService,
    has_active_subscription,
    subscription_plans,
    user_ai_daily_limit,
)
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
ImageUploadDep = Annotated[UploadFile, File()]
OptionalTextHintDep = Annotated[str | None, Form()]


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

    return await _ai_usage_summary(user, AIUsageService(session))


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
    weekly_missions = await GrowthService(session).weekly_missions(user)
    return WebAppToday(
        user=user,
        diary=diary,
        water_ml=await wellness.today_water_ml(user),
        latest_weight_kg=latest_weight.weight_kg if latest_weight else user.weight,
        ai_usage=await _ai_usage_summary(user, usage_service),
        onboarding_completed=user.onboarding_completed,
        has_active_subscription=has_active_subscription(user),
        subscription_plan=user.subscription_plan,
        subscription_expires_at=user.subscription_expires_at,
        subscription_days_left=_subscription_days_left(user),
        weight_goal=weight_goal_summary(user),
        weekly_missions=WebAppWeeklyMissions(
            week_start=weekly_missions.week_start,
            missions=[
                WebAppWeeklyMission(
                    key=mission.key,
                    title=mission.title,
                    current=mission.current,
                    target=mission.target,
                    completed=mission.completed,
                )
                for mission in weekly_missions.missions
            ],
            completed_count=weekly_missions.completed_count,
            eligible_for_bonus=weekly_missions.eligible_for_bonus,
            bonus_claimed=weekly_missions.bonus_claimed,
        ),
    )


@router.post("/webapp/me/entries", response_model=FoodEntryRead)
async def webapp_create_entry(
    payload: FoodEntryCreate,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> FoodEntryRead:
    if payload.source not in {"manual", "ai_photo", "food_search", "barcode", "history"}:
        raise HTTPException(status_code=400, detail="Unsupported food entry source")
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    return await DiaryService(session).add_entry(user, payload)


@router.post("/webapp/me/food/parse-text", response_model=WebAppFoodTextParseResult)
async def webapp_parse_food_text(
    payload: WebAppFoodTextParse,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> WebAppFoodTextParseResult:
    text = " ".join(payload.text.split())
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    diary = DiaryService(session)

    history_entry = await diary.recent_matching_entry(user, text)
    if history_entry is not None:
        return WebAppFoodTextParseResult(
            foods=[estimate_from_entry(history_entry)],
            source="history",
            ai_used=False,
            remaining_ai_today=await _remaining_ai_for_webapp(user, AIUsageService(session)),
        )

    common_estimate = None if _should_parse_food_text_with_ai(text) else estimate_common_food(text)
    if common_estimate is not None:
        common_estimate.source_label = "База"
        return WebAppFoodTextParseResult(
            foods=[common_estimate],
            source="common",
            ai_used=False,
            remaining_ai_today=await _remaining_ai_for_webapp(user, AIUsageService(session)),
        )

    usage = AIUsageService(session)
    try:
        await _ensure_webapp_ai_allowed(user, usage)
    except AILimitReachedError as exc:
        raise HTTPException(status_code=402, detail="AI limit reached") from exc

    try:
        estimates = await AIFoodService().parse_text(text)
    except Exception as exc:
        logger.exception("Web app AI text food parse failed")
        raise HTTPException(status_code=503, detail="AI food parsing failed") from exc

    await usage.record_request(user, "webapp_manual_text")
    if not estimates.foods:
        raise HTTPException(status_code=422, detail="Food was not recognized")

    return WebAppFoodTextParseResult(
        foods=estimates.foods,
        source="ai",
        ai_used=True,
        remaining_ai_today=await _remaining_ai_for_webapp(user, usage),
    )


@router.post("/webapp/me/food/parse-photo", response_model=WebAppFoodTextParseResult)
async def webapp_parse_food_photo(
    identity: WebAppIdentityDep,
    session: SessionDep,
    image: ImageUploadDep,
    text_hint: OptionalTextHintDep = None,
) -> WebAppFoodTextParseResult:
    content_type = image.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Upload an image")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image is empty")
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image is too large")

    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    usage = AIUsageService(session)
    try:
        await _ensure_webapp_ai_allowed(user, usage)
    except AILimitReachedError as exc:
        raise HTTPException(status_code=402, detail="AI limit reached") from exc

    try:
        estimates = await AIFoodService().recognize_photo(
            image_bytes,
            mime_type=content_type,
            text_hint=text_hint,
        )
    except Exception as exc:
        logger.exception("Web app AI photo food parse failed")
        raise HTTPException(status_code=503, detail="AI photo parsing failed") from exc

    await usage.record_request(user, "webapp_photo")
    if not estimates.foods or (estimates.foods[0].confidence or 0) < 0.35:
        raise HTTPException(status_code=422, detail="Food was not recognized")

    photo_thumb_data_url = _make_photo_thumb_data_url(image_bytes)
    photo_thumb_expires_at = datetime.now(UTC) + timedelta(days=1)
    if photo_thumb_data_url:
        for food in estimates.foods:
            food.photo_thumb_data_url = photo_thumb_data_url
            food.photo_thumb_expires_at = photo_thumb_expires_at

    return WebAppFoodTextParseResult(
        foods=estimates.foods,
        source="photo",
        ai_used=True,
        remaining_ai_today=await _remaining_ai_for_webapp(user, usage),
    )


@router.post("/webapp/me/food/scan-barcode", response_model=WebAppFoodTextParseResult)
async def webapp_scan_barcode(
    identity: WebAppIdentityDep,
    session: SessionDep,
    image: ImageUploadDep,
) -> WebAppFoodTextParseResult:
    content_type = image.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Upload an image")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image is empty")
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image is too large")

    try:
        barcode = await asyncio.wait_for(
            asyncio.to_thread(BarcodeService().decode_image, image_bytes),
            timeout=8,
        )
    except (TimeoutError, BarcodeNotFoundError) as exc:
        raise HTTPException(status_code=422, detail="Barcode was not recognized") from exc

    return await _webapp_barcode_result(barcode, identity, session)


@router.post("/webapp/me/food/barcode", response_model=WebAppFoodTextParseResult)
async def webapp_lookup_barcode(
    payload: WebAppBarcodeLookup,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> WebAppFoodTextParseResult:
    barcode = normalize_barcode(payload.code)
    if barcode is None:
        raise HTTPException(status_code=422, detail="Barcode is invalid")
    return await _webapp_barcode_result(barcode, identity, session)


@router.get("/webapp/me/food/search", response_model=WebAppFoodTextParseResult)
async def webapp_search_food(
    identity: WebAppIdentityDep,
    session: SessionDep,
    query: str = Query(min_length=2, max_length=80),
    force_ai: bool = Query(default=False),
) -> WebAppFoodTextParseResult:
    text = " ".join(query.split())
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    diary = DiaryService(session)
    estimates: list[FoodEstimate] = []

    history_entry = await diary.recent_matching_entry(user, text)
    if history_entry is not None:
        history_estimate = estimate_from_entry(history_entry)
        history_estimate.source_label = "История"
        estimates.append(history_estimate)

    catalog = FoodCatalogService(session)
    estimates.extend(await catalog.search(user, text, limit=8))

    common_estimate = estimate_common_food(text)
    if common_estimate is not None:
        common_estimate.source_label = "База"
        estimates.append(common_estimate)

    try:
        openfood_estimates = await asyncio.wait_for(
            OpenFoodFactsService(session).search_products(text, limit=8),
            timeout=settings.food_search_openfoodfacts_timeout_seconds,
        )
        for estimate in openfood_estimates:
            estimate.source_label = "База"
        estimates.extend(openfood_estimates)
    except TimeoutError:
        logger.info("Web app OpenFoodFacts search timed out query=%r", text)
    except Exception:
        logger.debug("Web app OpenFoodFacts search failed", exc_info=True)

    if len(estimates) < 4:
        try:
            fatsecret_estimates = await asyncio.wait_for(
                FatSecretService().search_products(text, limit=8),
                timeout=settings.food_search_fatsecret_timeout_seconds,
            )
            for estimate in fatsecret_estimates:
                estimate.source_label = "База"
            estimates.extend(fatsecret_estimates)
        except TimeoutError:
            logger.info("Web app FatSecret search timed out query=%r", text)
        except Exception:
            logger.debug("Web app FatSecret search failed", exc_info=True)

    ai_used = False
    usage = AIUsageService(session)
    deduped = _dedupe_food_estimates(estimates, limit=8)
    if (force_ai or not deduped) and len(text) >= 4 and normalize_barcode(text) is None:
        try:
            await _ensure_webapp_ai_allowed(user, usage)
            ai_estimates = await AIFoodService().parse_text(text)
            await usage.record_request(user, "webapp_food_search_ai")
            ai_used = True
            deduped = _dedupe_food_estimates(mark_ai_suggestions(ai_estimates.foods), limit=3)
        except AILimitReachedError as exc:
            if force_ai:
                raise HTTPException(status_code=402, detail="AI limit reached") from exc
            logger.info("Web app food search AI suggestion skipped: limit reached")
        except Exception:
            logger.debug("Web app food search AI suggestion failed", exc_info=True)

    return WebAppFoodTextParseResult(
        foods=deduped,
        source="food_search",
        ai_used=ai_used,
        remaining_ai_today=await _remaining_ai_for_webapp(user, usage),
    )


@router.post("/webapp/me/food/refine", response_model=WebAppFoodTextParseResult)
async def webapp_refine_food(
    payload: WebAppFoodRefine,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> WebAppFoodTextParseResult:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    usage = AIUsageService(session)
    try:
        await _ensure_webapp_ai_allowed(user, usage)
    except AILimitReachedError as exc:
        raise HTTPException(status_code=402, detail="AI limit reached") from exc

    try:
        estimates = await AIFoodService().refine_estimate(payload.estimate, payload.text)
    except Exception as exc:
        logger.exception("Web app AI food refinement failed")
        raise HTTPException(status_code=503, detail="AI food refinement failed") from exc

    await usage.record_request(user, "webapp_food_refine")
    if not estimates.foods:
        raise HTTPException(status_code=422, detail="Food was not recognized")

    return WebAppFoodTextParseResult(
        foods=[estimates.foods[0]],
        source=payload.source,
        ai_used=True,
        remaining_ai_today=await _remaining_ai_for_webapp(user, usage),
    )


@router.post("/webapp/me/quality-events")
async def webapp_record_quality_event(
    payload: WebAppQualityEventCreate,
    identity: WebAppIdentityDep,
) -> dict[str, bool]:
    await record_quality_event(
        payload.event_type,
        telegram_id=identity.telegram_id,
        username=identity.username,
        source=payload.source,
        query=payload.query,
        details=payload.details,
        notify_admin=payload.event_type
        in {"webapp_ai_reject", "webapp_ai_failed", "webapp_search_failed", "webapp_barcode_failed"},
    )
    return {"ok": True}


@router.post("/webapp/me/promos/validate", response_model=WebAppPromoValidateResult)
async def webapp_validate_promo(
    payload: WebAppPromoValidate,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> WebAppPromoValidateResult:
    await UserService(session).get_or_create(identity.telegram_id, identity.username)
    discount = await SubscriptionService(session).get_valid_promo(payload.code)
    if discount is None:
        return WebAppPromoValidateResult(valid=False)

    return WebAppPromoValidateResult(
        valid=True,
        code=discount.code,
        discount_percent=discount.discount_percent,
        plans=[
            WebAppPromoPlan(
                code=plan.code,
                title=plan.title,
                rub=discount.apply_to_rub(plan.rub),
                stars=discount.apply_to_stars(plan.stars),
                daily_limit=plan.daily_limit,
            )
            for plan in subscription_plans().values()
        ],
    )


@router.get("/webapp/me/subscription/plans", response_model=WebAppSubscriptionPlans)
async def webapp_subscription_plans(
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> WebAppSubscriptionPlans:
    await UserService(session).get_or_create(identity.telegram_id, identity.username)
    return WebAppSubscriptionPlans(
        plans=[
            WebAppPromoPlan(
                code=plan.code,
                title=plan.title,
                rub=plan.rub,
                stars=plan.stars,
                daily_limit=plan.daily_limit,
            )
            for plan in subscription_plans().values()
        ]
    )


def _should_parse_food_text_with_ai(text: str) -> bool:
    normalized = text.casefold()
    tokens = re.findall(r"[0-9a-zа-яё]+", normalized)
    if len(tokens) >= 4:
        return True
    return any(separator in normalized for separator in (" и ", ",", "+", " плюс ", " с "))


async def _webapp_barcode_result(
    barcode: str,
    identity: WebAppIdentity,
    session: AsyncSession,
) -> WebAppFoodTextParseResult:
    await UserService(session).get_or_create(identity.telegram_id, identity.username)
    try:
        product = await OpenFoodFactsService(session).get_product(barcode)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Product was not found") from exc

    return WebAppFoodTextParseResult(
        foods=[_estimate_from_product_cache(product)],
        source="barcode",
        ai_used=False,
        remaining_ai_today=None,
        barcode=barcode,
    )


def _estimate_from_product_cache(product: Any) -> FoodEstimate:
    estimate = enrich_food_payload(
        FoodEstimate(
            name=product.product_name,
            weight_g=100,
            kcal=product.kcal_100g or 0,
            protein=product.protein_100g or 0,
            fat=product.fat_100g or 0,
            carbs=product.carbs_100g or 0,
            confidence=0.9,
            source_label="Штрихкод",
        )
    )
    return estimate


def _dedupe_food_estimates(estimates: list[FoodEstimate], *, limit: int) -> list[FoodEstimate]:
    deduped: list[FoodEstimate] = []
    seen: set[str] = set()
    for estimate in estimates:
        key = f"{estimate.name.casefold()}:{round(estimate.kcal or 0)}:{round(estimate.weight_g or 0)}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(enrich_food_payload(estimate))
    return deduped[:limit]


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


@router.post("/webapp/me/onboarding", response_model=WebAppToday)
async def webapp_complete_onboarding(
    payload: WebAppOnboardingComplete,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> WebAppToday:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    user.goal = payload.goal
    user.gender = payload.gender
    user.age = payload.age
    user.height = payload.height
    user.weight = payload.weight
    user.activity = payload.activity
    user.target_weight_kg = None if payload.goal == "maintain" else payload.target_weight_kg
    user.weekly_weight_change_kg = None if payload.goal == "maintain" else payload.weekly_weight_change_kg
    user.daily_kcal_target = calculate_daily_kcal_target(user)
    apply_default_macro_targets(user)
    user.onboarding_completed = True
    await session.commit()
    await session.refresh(user)
    return await webapp_today(identity, session)


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


@router.put("/webapp/me/entries/{entry_id}", response_model=FoodEntryRead)
async def webapp_update_entry(
    entry_id: int,
    payload: FoodEntryUpdate,
    identity: WebAppIdentityDep,
    session: SessionDep,
) -> FoodEntryRead:
    user = await UserService(session).get_or_create(identity.telegram_id, identity.username)
    entry = await DiaryService(session).update_entry_payload(
        user,
        entry_id,
        FoodEntryCreate(
            **payload.model_dump(),
            source="manual",
        ),
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return FoodEntryRead.model_validate(entry)


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


def _make_photo_thumb_data_url(image_bytes: bytes) -> str | None:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            image.thumbnail((360, 360), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=68, optimize=True)
    except Exception:
        logger.debug("Failed to create food photo thumbnail", exc_info=True)
        return None
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    data_url = f"data:image/jpeg;base64,{encoded}"
    return data_url if len(data_url) <= 70000 else None


async def _ai_usage_summary(user, usage_service: AIUsageService) -> AIUsageSummary:
    used_today = await usage_service.today_count(user)
    daily_limit = user_ai_daily_limit(user)
    daily_remaining = 10**9 if daily_limit is None else max(daily_limit - used_today, 0)
    if has_active_subscription(user):
        return AIUsageSummary(
            used_today=used_today,
            remaining_today=daily_remaining,
            daily_limit=0 if daily_limit is None else daily_limit,
        )

    lifetime_used = await usage_service.lifetime_count(user)
    trial_remaining = max(settings.ai_trial_request_limit - lifetime_used, 0)
    return AIUsageSummary(
        used_today=used_today,
        remaining_today=min(daily_remaining, trial_remaining),
        daily_limit=0 if daily_limit is None else daily_limit,
        trial_used=lifetime_used,
        trial_remaining=trial_remaining,
        trial_limit=settings.ai_trial_request_limit,
        is_trial=True,
    )


def _subscription_days_left(user) -> int | None:
    if not has_active_subscription(user) or user.subscription_expires_at is None:
        return None
    expires_at = user.subscription_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    delta = expires_at - datetime.now(UTC)
    return max(0, delta.days + (1 if delta.seconds else 0))


async def _remaining_ai_for_webapp(user, usage_service: AIUsageService) -> int:
    if has_active_subscription(user):
        return await usage_service.remaining_today(user)
    return min(await usage_service.remaining_today(user), await usage_service.remaining_trial(user))


async def _ensure_webapp_ai_allowed(user, usage_service: AIUsageService, request_count: int = 1) -> None:
    if has_active_subscription(user):
        await usage_service.ensure_allowed(user, request_count=request_count)
        return
    await usage_service.ensure_trial_allowed(user, request_count=request_count)


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

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from kcal_tracker.config import settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.services.product_analytics import (
    AIQualityMetrics,
    FunnelMetrics,
    ProductAnalyticsService,
    RetentionMetrics,
)


async def product_analytics_text() -> str:
    tz = ZoneInfo(settings.default_timezone)
    today_start, today_end = _today_bounds(tz)
    week_start = today_start - timedelta(days=6)
    month_start = today_start - timedelta(days=29)
    async with SessionLocal() as session:
        analytics = ProductAnalyticsService(session)
        today_quality = await analytics.ai_quality(today_start, today_end)
        week_quality = await analytics.ai_quality(week_start, today_end)
        month_quality = await analytics.ai_quality(month_start, today_end)
        today_funnel = await analytics.funnel(today_start, today_end)
        week_funnel = await analytics.funnel(week_start, today_end)
        month_funnel = await analytics.funnel(month_start, today_end)
        today_retention = await analytics.retention(today_start, today_end)
        week_retention = await analytics.retention(week_start, today_end)
        month_retention = await analytics.retention(month_start, today_end)
    return "\n".join(
        [
            "📈 Product analytics",
            "",
            product_period_text("Сегодня", today_quality, today_funnel, today_retention),
            "",
            product_period_text("7 дней", week_quality, week_funnel, week_retention),
            "",
            product_period_text("30 дней", month_quality, month_funnel, month_retention),
        ]
    )


def product_period_text(
    title: str,
    quality: AIQualityMetrics,
    funnel: FunnelMetrics,
    retention: RetentionMetrics,
) -> str:
    return "\n".join(
        [
            title,
            (
                "AI quality: "
                f"ok {quality.accepted}, edit {quality.edited}, "
                f"reject {quality.rejected}, fail {quality.failed}"
            ),
            (
                "AI rates: "
                f"accept {_optional_percent(quality.acceptance_rate)}, "
                f"edit {_optional_percent(quality.edit_rate)}, "
                f"fail {_optional_percent(quality.failure_rate)}"
            ),
            (
                "Landing: "
                f"views {funnel.landing_views}, clicks {funnel.bot_clicks} "
                f"({_optional_percent(funnel.landing_to_bot_rate)})"
            ),
            (
                "Onboarding: "
                f"{funnel.onboarded_users}/{funnel.new_users} "
                f"({_optional_percent(funnel.onboarding_rate)})"
            ),
            (
                "Retention: "
                f"D1 {retention.d1_users}/{retention.cohort_users} "
                f"({_optional_percent(retention.d1_rate)}), "
                f"D7 {retention.d7_users}/{retention.cohort_users} "
                f"({_optional_percent(retention.d7_rate)})"
            ),
            (
                "Paywall: "
                f"{funnel.payment_starts}/{funnel.paywall_opens} starts "
                f"({_optional_percent(funnel.paywall_to_payment_start_rate)}), "
                f"{funnel.successful_payments} paid "
                f"({_optional_percent(funnel.payment_success_rate)})"
            ),
        ]
    )


def _optional_percent(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.0%}"


def _today_bounds(tz: ZoneInfo) -> tuple[datetime, datetime]:
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start, end

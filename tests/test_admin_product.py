from __future__ import annotations

from kcal_tracker.admin_bot.product import product_period_text
from kcal_tracker.services.product_analytics import (
    AIQualityMetrics,
    FunnelMetrics,
    RetentionMetrics,
)


def test_product_period_text_formats_quality_and_funnel_rates() -> None:
    text = product_period_text(
        "7 дней",
        AIQualityMetrics(accepted=7, edited=2, rejected=1, failed=5),
        FunnelMetrics(
            landing_views=100,
            bot_clicks=25,
            new_users=20,
            onboarded_users=15,
            paywall_opens=10,
            payment_starts=4,
            successful_payments=3,
        ),
        RetentionMetrics(cohort_users=20, d1_users=8, d7_users=5),
    )

    assert "7 дней" in text
    assert "AI quality: ok 7, edit 2, reject 1, fail 5" in text
    assert "accept 70%, edit 20%, fail 33%" in text
    assert "views 100, clicks 25 (25%)" in text
    assert "15/20 (75%)" in text
    assert "D1 8/20 (40%), D7 5/20 (25%)" in text
    assert "4/10 starts (40%), 3 paid (75%)" in text


def test_product_period_text_handles_empty_denominators() -> None:
    text = product_period_text(
        "Сегодня",
        AIQualityMetrics(accepted=0, edited=0, rejected=0, failed=0),
        FunnelMetrics(
            landing_views=0,
            bot_clicks=0,
            new_users=0,
            onboarded_users=0,
            paywall_opens=0,
            payment_starts=0,
            successful_payments=0,
        ),
        RetentionMetrics(cohort_users=0, d1_users=0, d7_users=0),
    )

    assert "accept —, edit —, fail —" in text
    assert "views 0, clicks 0 (—)" in text
    assert "0/0 (—)" in text

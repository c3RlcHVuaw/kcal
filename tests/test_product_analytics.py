from __future__ import annotations

from kcal_tracker.services.product_analytics import (
    AI_ACCEPT_EVENTS,
    AI_EDIT_EVENTS,
    AIQualityMetrics,
    FunnelMetrics,
    RetentionMetrics,
)


def test_ai_quality_metrics_rates_use_reviewed_events() -> None:
    metrics = AIQualityMetrics(accepted=7, edited=2, rejected=1, failed=5)

    assert metrics.reviewed == 10
    assert metrics.total_signals == 15
    assert metrics.acceptance_rate == 0.7
    assert metrics.edit_rate == 0.2
    assert metrics.failure_rate == 5 / 15


def test_ai_quality_metrics_rates_are_empty_without_signals() -> None:
    metrics = AIQualityMetrics(accepted=0, edited=0, rejected=0, failed=0)

    assert metrics.acceptance_rate is None
    assert metrics.edit_rate is None
    assert metrics.failure_rate is None


def test_funnel_metrics_rates() -> None:
    metrics = FunnelMetrics(
        landing_views=100,
        bot_clicks=25,
        new_users=20,
        onboarded_users=15,
        paywall_opens=10,
        payment_starts=4,
        successful_payments=3,
    )

    assert metrics.landing_to_bot_rate == 0.25
    assert metrics.onboarding_rate == 0.75
    assert metrics.paywall_to_payment_start_rate == 0.4
    assert metrics.payment_success_rate == 0.75


def test_retention_metrics_rates() -> None:
    metrics = RetentionMetrics(cohort_users=20, d1_users=8, d7_users=5)

    assert metrics.d1_rate == 0.4
    assert metrics.d7_rate == 0.25


def test_retention_metrics_rates_are_empty_without_cohort() -> None:
    metrics = RetentionMetrics(cohort_users=0, d1_users=0, d7_users=0)

    assert metrics.d1_rate is None
    assert metrics.d7_rate is None


def test_ai_quality_event_contract_includes_webapp_save_outcomes() -> None:
    assert "webapp_ai_saved_unedited" in AI_ACCEPT_EVENTS
    assert "webapp_ai_adjust" in AI_EDIT_EVENTS
    assert "webapp_ai_saved_edited" in AI_EDIT_EVENTS

from __future__ import annotations

from pathlib import Path

WEBAPP_APP_JS = Path("src/kcal_tracker/webapp_static/app.js")


def test_webapp_onboarding_and_nudge_events_are_tracked() -> None:
    app_js = WEBAPP_APP_JS.read_text()

    assert "webapp_onboarding_complete" in app_js
    assert "webapp_onboarding_tour_open" in app_js
    assert "webapp_onboarding_start_food" in app_js
    assert "webapp_smart_nudge_click" in app_js

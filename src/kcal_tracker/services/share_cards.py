from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from kcal_tracker.services.diary import WeeklyAnalytics
from kcal_tracker.services.growth import WeeklyMissions
from kcal_tracker.services.nutrition import weekly_score


def weekly_progress_card(
    analytics: WeeklyAnalytics,
    missions: WeeklyMissions,
    referral_link: str,
) -> bytes:
    width, height = 1200, 675
    image = Image.new("RGB", (width, height), "#f7f4ed")
    draw = ImageDraw.Draw(image)
    title_font = _font(58)
    big_font = _font(86)
    body_font = _font(34)
    small_font = _font(28)

    draw.rounded_rectangle((44, 44, width - 44, height - 44), radius=34, fill="#fffdf8")
    draw.text((82, 76), "Kcal · недельный прогресс", fill="#2f2b24", font=title_font)
    draw.text((82, 168), f"{weekly_score(analytics)}/10", fill="#1e7665", font=big_font)
    draw.text((310, 196), "оценка недели", fill="#70695e", font=body_font)

    stats = [
        ("Среднее", f"{analytics.average_kcal:.0f} / {analytics.target_kcal} ккал"),
        ("Дни у цели", f"{analytics.days_in_target} из {len(analytics.days)}"),
        ("Миссии", f"{missions.completed_count} из {len(missions.missions)}"),
    ]
    x = 82
    for label, value in stats:
        draw.rounded_rectangle((x, 330, x + 310, 450), radius=22, fill="#f1eadf")
        draw.text((x + 24, 352), label, fill="#70695e", font=small_font)
        draw.text((x + 24, 392), value, fill="#2f2b24", font=body_font)
        x += 340

    mission_text = ", ".join(
        f"{mission.title}: {min(mission.current, mission.target)}/{mission.target}"
        for mission in missions.missions[:3]
    )
    draw.text((82, 508), mission_text, fill="#2f2b24", font=small_font)
    draw.text((82, 568), f"Попробуй тоже: {referral_link}", fill="#1e7665", font=small_font)

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()

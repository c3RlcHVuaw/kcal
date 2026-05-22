from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from kcal_tracker.services.diary import WeeklyAnalytics
from kcal_tracker.services.food_insights import food_label
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
        ("Среднее", f"{analytics.average_kcal:.0f} / {analytics.target_kcal} ккал", 350),
        ("Дни у цели", f"{analytics.days_in_target} из {len(analytics.days)}", 280),
        ("Миссии", f"{missions.completed_count} из {len(missions.missions)}", 280),
    ]
    x = 82
    for label, value, card_width in stats:
        draw.rounded_rectangle((x, 330, x + card_width, 450), radius=22, fill="#f1eadf")
        draw.text((x + 24, 352), label, fill="#70695e", font=small_font)
        draw.text((x + 24, 392), value, fill="#2f2b24", font=body_font)
        x += card_width + 32

    mission_text = ", ".join(
        f"{mission.title}: {min(mission.current, mission.target)}/{mission.target}"
        for mission in missions.missions[:3]
    )
    draw.text((82, 508), mission_text, fill="#2f2b24", font=small_font)
    draw.text((82, 568), f"Попробуй тоже: {referral_link}", fill="#1e7665", font=small_font)

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def daily_progress_card(
    summary,
    *,
    date_label: str,
    water_ml: int,
    activities=None,
) -> bytes:
    activities = activities or []
    width, height = 1200, 675
    image = Image.new("RGB", (width, height), "#f4f6f2")
    draw = ImageDraw.Draw(image)
    title_font = _font(56)
    big_font = _font(78)
    body_font = _font(34)
    small_font = _font(27)

    draw.rounded_rectangle((44, 44, width - 44, height - 44), radius=34, fill="#fffefa")
    draw.text((82, 76), f"Kcal · итог дня · {date_label}", fill="#2b2d2a", font=title_font)
    draw.text(
        (82, 165),
        f"{summary.kcal:.0f} / {summary.target_kcal} ккал",
        fill="#1d6f5f",
        font=big_font,
    )
    draw.text((82, 260), _daily_status(summary), fill="#6d675f", font=body_font)

    stats = [
        ("Белки", f"{summary.protein:.0f}/{summary.target_protein:.0f} г"),
        ("Жиры", f"{summary.fat:.0f}/{summary.target_fat:.0f} г"),
        ("Углеводы", f"{summary.carbs:.0f}/{summary.target_carbs:.0f} г"),
        ("Вода", f"{water_ml} мл"),
    ]
    x = 82
    for label, value in stats:
        draw.rounded_rectangle((x, 338, x + 244, 448), radius=20, fill="#e9efe6")
        draw.text((x + 22, 358), label, fill="#6d675f", font=small_font)
        draw.text((x + 22, 397), value, fill="#2b2d2a", font=body_font)
        x += 266

    top_entries = sorted(summary.entries, key=lambda entry: entry.kcal, reverse=True)[:3]
    if top_entries:
        draw.text((82, 502), "Что дало больше всего:", fill="#2b2d2a", font=body_font)
        foods = ", ".join(f"{food_label(entry)} {entry.kcal:.0f}" for entry in top_entries)
        draw.text((82, 552), foods[:92], fill="#6d675f", font=small_font)
    else:
        draw.text((82, 520), "Записей еды за день не было.", fill="#6d675f", font=body_font)

    activity_kcal = sum(activity.kcal for activity in activities)
    if activity_kcal:
        draw.text((842, 520), f"Активность: {activity_kcal:.0f} ккал", fill="#1d6f5f", font=small_font)

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _daily_status(summary) -> str:
    if not summary.entries:
        return "мало данных"
    delta = summary.kcal - summary.target_kcal
    if abs(delta) <= 150:
        return "в цель"
    if delta < 0:
        return "ниже цели"
    return "выше цели"


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

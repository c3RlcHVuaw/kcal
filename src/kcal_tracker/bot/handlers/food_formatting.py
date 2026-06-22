from __future__ import annotations

import re

from kcal_tracker.schemas import FoodEstimate, FoodEstimateList
from kcal_tracker.services.food_insights import food_label


def format_estimate_confirmation(
    estimate: FoodEstimate,
    *,
    show_portion_hint: bool = False,
    intro: str = "Я нашёл:",
) -> str:
    lines = [
        intro,
        "",
        f"{food_label(estimate)} — {estimate.weight_g or 0:.0f}г",
        f"🔥 {estimate.kcal:.0f} ккал",
        f"Б {estimate.protein:.0f} / Ж {estimate.fat:.0f} / У {estimate.carbs:.0f} г",
    ]
    if estimate.advice:
        lines.extend(["", f"💡 {estimate.advice}"])
    if estimate.confidence is not None and estimate.confidence < 0.7:
        lines.extend(["", "Оценка примерная, проверь граммовку перед сохранением."])
    if show_portion_hint:
        lines.extend(
            [
                "",
                "Проверь фото-вопросы: вся ли это порция, было ли масло/соус, "
                "сыр, сахар или напиток рядом. Если да — уточни перед сохранением.",
            ]
        )
    lines.extend(["", "Добавить в дневник?"])
    return "\n".join(lines)


def looks_like_complex_food(name: str) -> bool:
    normalized = name.casefold()
    complex_words = (
        "шаурм",
        "паста",
        "салат",
        "суп",
        "пицц",
        "бургер",
        "ролл",
        "плов",
        "каша",
        "греч",
        "рис",
        "куриц",
        "мясо",
        "гарнир",
        "соус",
        "боул",
        "сэндвич",
        "омлет",
    )
    if any(word in normalized for word in complex_words):
        return True
    return " с " in f" {normalized} " or " и " in f" {normalized} "


def format_search_results(estimates: list[FoodEstimate], *, query: str) -> str:
    lines = [
        f"По запросу «{query}» нашёл варианты в базе.",
        "Выбери только если продукт действительно похож:",
        "",
    ]
    for index, estimate in enumerate(estimates, start=1):
        label = f" · {estimate.source_label}" if estimate.source_label else ""
        lines.append(
            f"#{index} {food_label(estimate)} — {estimate.weight_g or 100:.0f}г, "
            f"{estimate.kcal:.0f} ккал{label}"
        )
        lines.append(
            f"   Б {estimate.protein:.0f} / Ж {estimate.fat:.0f} / У {estimate.carbs:.0f} г"
        )
    lines.extend(["", "Если ничего не подходит, нажми AI-разбор или напиши точнее."])
    return "\n".join(lines)


def plural_ru(value: int, one: str, few: str, many: str) -> str:
    value = abs(value) % 100
    if 11 <= value <= 14:
        return many
    last = value % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def format_multi_foods(
    estimates: FoodEstimateList,
    added_indices: set[int] | None = None,
) -> str:
    added_indices = added_indices or set()
    total = len(estimates.foods)
    added_count = len(added_indices)
    lines = [f"Нашёл {total} {plural_ru(total, 'позицию', 'позиции', 'позиций')}"]
    if added_count:
        lines.append(f"Добавлено: {added_count}/{total}")
    lines.append("")
    for index, estimate in enumerate(estimates.foods, start=1):
        is_added = index - 1 in added_indices
        marker = "✓ Добавлено" if is_added else f"#{index}"
        weight = f", {estimate.weight_g:.0f}г" if estimate.weight_g else ""
        lines.append(
            f"{marker} {food_label(estimate)}{weight} — {estimate.kcal:.0f} ккал"
        )
        lines.append(f"Б {estimate.protein:.0f} / Ж {estimate.fat:.0f} / У {estimate.carbs:.0f} г")
        if estimate.advice:
            lines.append(f"Совет: {estimate.advice}")
        lines.append("")
    lines.append("Добавь нужные позиции или всё сразу.")
    return "\n".join(lines)


def format_saved_food(
    estimate: FoodEstimate,
    *,
    summary=None,
    water_ml: int | None = None,
    duplicate: bool = False,
) -> str:
    prefix = "Уже добавлено" if duplicate else "Добавил"
    lines = [f"{prefix}: {food_label(estimate)} — {estimate.kcal:.0f} ккал."]
    if estimate.advice:
        lines.append(f"💡 {estimate.advice}")
    if summary is not None:
        lines.extend(["", after_food_progress_note(summary, water_ml)])
    return "\n".join(lines)


def after_food_progress_note(summary, water_ml: int | None = None) -> str:
    kcal_left = summary.target_kcal - summary.kcal
    protein_left = summary.target_protein - summary.protein
    if kcal_left < -150:
        return (
            f"Мини-цель: день выше плана на {abs(kcal_left):.0f} ккал, "
            "дальше просто выбираем что-то лёгкое и без компенсаций."
        )
    if protein_left > 25 and kcal_left > 150:
        return (
            f"Мини-цель: осталось около {kcal_left:.0f} ккал и "
            f"{protein_left:.0f}г белка. Хорошо зайдёт белковый приём."
        )
    if water_ml is not None and water_ml < 1000:
        return "Мини-цель: добавить воды, чтобы день ощущался ровнее."
    if kcal_left > 0:
        return f"Осталось около {kcal_left:.0f} ккал. Двигаемся спокойно."
    return "День близко к цели. Дальше без резких ограничений."


def parse_positive_float(value: str) -> float | None:
    try:
        parsed = float(value.replace(",", ".").strip())
    except ValueError:
        return None
    if parsed <= 0 or parsed > 10000:
        return None
    return parsed


def extract_requested_grams(value: str) -> float | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(?:г|гр|грамм|граммов)\b", value.casefold())
    if not match:
        return None
    try:
        grams = float(match.group(1).replace(",", "."))
    except ValueError:
        return None
    if grams <= 0 or grams > 10000:
        return None
    return grams


def scale_estimate(estimate: FoodEstimate, ratio: float) -> FoodEstimate:
    ratio = max(0.05, min(ratio, 10))
    if estimate.weight_g is not None:
        estimate.weight_g = round(estimate.weight_g * ratio, 1)
    estimate.kcal = round(estimate.kcal * ratio, 1)
    estimate.protein = round(estimate.protein * ratio, 1)
    estimate.fat = round(estimate.fat * ratio, 1)
    estimate.carbs = round(estimate.carbs * ratio, 1)
    if estimate.advice:
        estimate.advice = estimate.advice[:255]
    return estimate

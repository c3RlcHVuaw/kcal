from __future__ import annotations

from kcal_tracker.schemas import DiarySummary

HIGH_CALORIE_KCAL = 450
HIGH_CALORIE_DENSITY_PER_100G = 250


def remaining_advice(summary: DiarySummary) -> str:
    kcal_left = max(summary.target_kcal - summary.kcal, 0)
    protein_hint = (
        "омлет, курица или творог"
        if summary.protein < summary.target_protein
        else "овощи или легкий салат"
    )
    return f"До цели осталось примерно {kcal_left:.0f} ккал. Подойдут: {protein_hint}."


def diet_quality_note(summary: DiarySummary) -> str:
    notes: list[str] = []
    if summary.protein < summary.target_protein:
        notes.append(f"Белка осталось примерно {summary.target_protein - summary.protein:.0f}г.")
    if summary.kcal > summary.target_kcal:
        notes.append("Калории уже выше цели.")
    if summary.fat > summary.target_fat:
        notes.append("Жиры уже выше цели.")
    if not notes:
        notes.append("День выглядит ровно. Продолжаем спокойно.")
    return " ".join(notes)


def smart_evening_hint(summary: DiarySummary) -> str:
    kcal_left = summary.target_kcal - summary.kcal
    protein_left = summary.target_protein - summary.protein
    if protein_left > 25 and kcal_left > 150:
        return "На вечер просится белок: творог, йогурт, курица или яйца."
    if kcal_left > 250:
        return f"До цели осталось около {kcal_left:.0f} ккал."
    if kcal_left < -150:
        return "Калории уже выше цели. Дальше лучше что-то лёгкое."
    return "Вечер выглядит спокойно: можно просто закрыть день без суеты."


def smart_morning_hint(yesterday: DiarySummary) -> str:
    if not yesterday.entries:
        return "Вчера дневник пустой. Сегодня проще начать с завтрака и пары быстрых записей."

    kcal_delta = yesterday.kcal - yesterday.target_kcal
    protein_left = yesterday.target_protein - yesterday.protein
    if kcal_delta > 200:
        return (
            "Вчера калории были выше цели. "
            "Сегодня начни спокойно: белок, вода и без сладкого натощак."
        )
    if protein_left > 25:
        return "Вчера не добрали белок. На завтрак хорошо зайдут яйца, творог или йогурт."
    if yesterday.carbs > yesterday.target_carbs * 1.2:
        return "Вчера углеводов было многовато. Утром лучше добавить белок и клетчатку."
    return "Вчера день выглядел ровно. Сегодня держим тот же темп и отмечаем завтрак."


def smart_lunch_hint(summary: DiarySummary) -> str:
    if not summary.entries:
        return (
            "Если завтрак уже был, занеси его сейчас. "
            "На обед лучше собрать белок, крупу и овощи."
        )

    kcal_left = summary.target_kcal - summary.kcal
    protein_left = summary.target_protein - summary.protein
    if protein_left > 35 and kcal_left > 350:
        return "К обеду просится белок: курица, рыба, яйца, творог или бобовые."
    if kcal_left < 500:
        return "Калорий на день осталось немного. Обед лучше сделать легче и без сладких напитков."
    return f"До дневной цели примерно {max(kcal_left, 0):.0f} ккал. Самое время записать обед."


def is_high_calorie_food(item) -> bool:
    kcal = float(getattr(item, "kcal", 0) or 0)
    weight_g = getattr(item, "weight_g", None)
    if kcal >= HIGH_CALORIE_KCAL:
        return True
    if not weight_g or weight_g <= 0 or kcal < 250:
        return False
    return kcal / weight_g * 100 >= HIGH_CALORIE_DENSITY_PER_100G


def high_calorie_add_warning(summary: DiarySummary, item) -> str | None:
    if not is_high_calorie_food(item):
        return None

    high_calorie_count = sum(1 for entry in summary.entries if is_high_calorie_food(entry))
    projected_kcal = summary.kcal + float(getattr(item, "kcal", 0) or 0)
    close_to_target = summary.kcal >= summary.target_kcal * 0.75
    over_after_add = projected_kcal > summary.target_kcal
    many_high_calorie = high_calorie_count >= 2

    if not (many_high_calorie or close_to_target or over_after_add):
        return None

    reasons: list[str] = []
    if many_high_calorie:
        reasons.append(f"сегодня уже {high_calorie_count} калорийные позиции")
    if over_after_add:
        reasons.append(f"после добавления будет около {projected_kcal:.0f} ккал")
    elif close_to_target:
        reasons.append(f"сейчас уже {summary.kcal:.0f} из {summary.target_kcal} ккал")

    detail = "; ".join(reasons)
    return (
        "Похоже, день уже довольно плотный по калориям: "
        f"{detail}. Точно добавить ещё одну калорийную позицию?"
    )

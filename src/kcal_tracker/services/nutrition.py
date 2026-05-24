from __future__ import annotations

from typing import Any

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
        notes.append("Калории выше цели, без резких компенсаций.")
    if summary.fat > summary.target_fat:
        notes.append("Жиры выше плана, следующий приём можно сделать легче.")
    if not notes:
        notes.append("День выглядит ровно. Продолжаем спокойно.")
    return " ".join(notes)


def smart_problem_signals(summary: DiarySummary, water_ml: int = 0) -> list[str]:
    signals: list[str] = []
    kcal_left = summary.target_kcal - summary.kcal
    protein_left = summary.target_protein - summary.protein

    if kcal_left < -150:
        signals.append(f"Калории выше цели на {abs(kcal_left):.0f} ккал, это поправимо")
    elif abs(kcal_left) <= 150:
        signals.append("✅ Калории рядом с целью")
    elif kcal_left > 600 and summary.entries:
        signals.append(f"🍽 Осталось много калорий: около {kcal_left:.0f}")

    if protein_left > 30:
        signals.append(f"⚠️ Белка мало: осталось примерно {protein_left:.0f}г")
    elif protein_left <= 10 and summary.entries:
        signals.append("✅ Белок почти закрыт")

    if summary.fat > summary.target_fat + 10:
        signals.append("⚠️ Жиры выше плана")
    if water_ml and water_ml < 1000:
        signals.append("💧 Воды пока мало")

    if not signals:
        signals.append("✅ День выглядит спокойно")
    return signals[:2]


def weekly_score(analytics: Any) -> int:
    tracked_days = [day for day in analytics.days if day.entries_count]
    if not tracked_days:
        return 0

    score = 4
    score += min(3, analytics.days_in_target)

    average_delta = abs(analytics.average_kcal - analytics.target_kcal)
    if average_delta <= 150:
        score += 2
    elif average_delta <= 300:
        score += 1

    protein_days = sum(1 for day in tracked_days if day.protein >= 80)
    if protein_days >= max(2, len(tracked_days) // 2):
        score += 1

    return max(1, min(score, 10))


def smart_evening_hint(summary: DiarySummary) -> str:
    kcal_left = summary.target_kcal - summary.kcal
    protein_left = summary.target_protein - summary.protein
    if protein_left > 25 and kcal_left > 150:
        return "На вечер просится белок: творог, йогурт, курица или яйца."
    if kcal_left > 250:
        return f"До цели осталось около {kcal_left:.0f} ккал."
    if kcal_left < -150:
        return "Калории выше цели. Ничего страшного: дальше лучше что-то лёгкое."
    return "Вечер выглядит спокойно: можно просто закрыть день без суеты."


def smart_day_coach(summary: DiarySummary, water_ml: int = 0) -> str:
    if not summary.entries:
        return (
            "Пока дневник пустой. Начни с любого реального "
            "приёма пищи: "
            "даже примерная запись лучше, чем идеальная тишина."
        )

    kcal_delta = summary.kcal - summary.target_kcal
    protein_left = summary.target_protein - summary.protein
    fat_over = summary.fat - summary.target_fat
    carbs_over = summary.carbs - summary.target_carbs

    wins: list[str] = []
    if abs(kcal_delta) <= 150:
        wins.append("калории близко к цели")
    if protein_left <= 10:
        wins.append("белок почти закрыт")
    if water_ml >= 1500:
        wins.append("вода идёт нормально")

    risks: list[str] = []
    if kcal_delta > 150:
        risks.append("калории выше цели, без резких компенсаций")
    if protein_left > 25:
        risks.append("белка заметно не хватает")
    if fat_over > 10:
        risks.append("жиры перебраны")
    if carbs_over > 25:
        risks.append("углеводы выше плана")
    if kcal_delta <= 150 and summary.target_kcal - summary.kcal > 500:
        risks.append("до цели ещё большой зазор")
    if water_ml and water_ml < 1000:
        risks.append("воды пока мало")

    if risks:
        lead = f"Хорошо: {', '.join(wins)}. " if wins else ""
        return lead + f"Главный фокус сейчас: {risks[0]}."
    if wins:
        return (
            f"День выглядит ровно: {', '.join(wins)}. "
            "Продолжай без резких компенсаций."
        )
    return (
        "День пока нейтральный. Следующий приём пищи лучше "
        "собрать вокруг белка и овощей."
    )


def daily_focus(summary: DiarySummary, water_ml: int = 0) -> str:
    kcal_left = summary.target_kcal - summary.kcal
    protein_left = summary.target_protein - summary.protein
    if not summary.entries:
        return "записать первый приём пищи"
    if protein_left > 30 and kcal_left > 200:
        return "добрать белок"
    if summary.fat > summary.target_fat + 10:
        return (
            "держать следующий приём без масла, "
            "сыра и жареного"
        )
    if kcal_left < -150:
        return "закрыть день лёгкой едой и водой"
    if water_ml < 1200:
        return "добавить воды"
    if kcal_left > 500:
        return "не пропустить нормальный приём пищи"
    return "сохранить текущий темп"


def meal_suggestion_text(summary: DiarySummary, water_ml: int = 0) -> str:
    kcal_left = max(summary.target_kcal - summary.kcal, 0)
    protein_left = max(summary.target_protein - summary.protein, 0)

    lines = ["Что съесть сейчас:", ""]
    if kcal_left <= 150:
        lines.extend(
            [
                "Калорий почти не осталось. Лучше выбрать "
                "что-то очень лёгкое:",
                "1. Овощной салат без масла.",
                "2. Чай/вода и пауза 15 минут, если это тяга "
                "к перекусу.",
                "3. Небольшой йогурт без сахара, если реально "
                "голодно.",
            ]
        )
    elif protein_left >= 30:
        limit = min(kcal_left, 550)
        lines.extend(
            [
                f"До цели около {kcal_left:.0f} ккал, белка не хватает. "
                f"Варианты до {limit:.0f} ккал:",
                "1. Курица или рыба + овощи.",
                "2. Творог/греческий йогурт + ягоды.",
                "3. Омлет из 2-3 яиц с овощами.",
            ]
        )
    elif summary.fat > summary.target_fat:
        lines.extend(
            [
                "Жиры уже выше плана, поэтому лучше без масла и жареного. "
                f"Осталось около {kcal_left:.0f} ккал:",
                "1. Рис/гречка + курица или тунец.",
                "2. Овощной суп + кусок хлеба.",
                "3. Йогурт без сахара + фрукт.",
            ]
        )
    elif kcal_left >= 500:
        lines.extend(
            [
                "Можно собрать нормальный приём пищи примерно "
                "на 400-550 ккал:",
                "1. Белок + крупа + овощи.",
                "2. Суп + хлеб + йогурт.",
                "3. Паста/рис с нежирным белком и овощами.",
            ]
        )
    else:
        lines.extend(
            [
                f"Осталось около {kcal_left:.0f} ккал. "
                "Подойдут спокойные варианты:",
                "1. Творог или йогурт.",
                "2. Яйца + овощи.",
                "3. Фрукт + белковое дополнение.",
            ]
        )

    if water_ml < 1000:
        lines.append("")
        lines.append(
            "И добавь стакан воды: сегодня её пока мало."
        )
    return "\n".join(lines)


def weekly_coach_note(analytics: Any) -> str:
    tracked_days = [day for day in analytics.days if day.entries_count]
    if not tracked_days:
        return (
            "AI-разбор недели: пока мало данных. Отмечай еду "
            "3-4 дня, и появятся нормальные выводы."
        )

    average_delta = analytics.average_kcal - analytics.target_kcal
    protein_days = sum(1 for day in tracked_days if day.protein >= 80)
    high_fat_days = sum(1 for day in tracked_days if day.fat >= 90)
    high_carb_days = sum(1 for day in tracked_days if day.carbs >= 280)

    notes: list[str] = []
    if average_delta > 150:
        notes.append(f"в среднем перебор около {average_delta:.0f} ккал")
    elif average_delta < -250:
        notes.append(
            f"в среднем недобор около {abs(average_delta):.0f} ккал"
        )
    else:
        notes.append("средняя калорийность близко к цели")

    if protein_days < max(2, len(tracked_days) // 2):
        notes.append("белок стоит сделать главным фокусом")
    if high_fat_days >= 3:
        notes.append("часто набираются жиры")
    if high_carb_days >= 3:
        notes.append("углеводы часто высокие")
    if analytics.days_in_target >= max(2, len(tracked_days) // 2):
        notes.append("много дней рядом с целью")

    return "AI-разбор недели: " + "; ".join(notes) + "."


def end_of_day_forecast(summary: DiarySummary, patterns: Any | None = None) -> str | None:
    if not summary.entries:
        return None

    usual_evening_kcal = float(getattr(patterns, "average_evening_kcal", 0) or 0)
    tracked_days = int(getattr(patterns, "tracked_days", 0) or 0)
    if tracked_days < 3 or usual_evening_kcal < 150:
        usual_evening_kcal = 450

    projected_kcal = summary.kcal + usual_evening_kcal
    projected_delta = projected_kcal - summary.target_kcal
    if projected_delta > 150:
        return (
            "Прогноз: если ужин будет как обычно, "
            "день может выйти "
            f"в плюс примерно на {projected_delta:.0f} ккал."
        )
    if projected_delta < -250:
        return (
            "Прогноз: даже с обычным ужином останется "
            "запас около "
            f"{abs(projected_delta):.0f} ккал."
        )
    return (
        "Прогноз: с обычным ужином день, скорее всего, "
        "останется рядом с целью."
    )


def automatic_pattern_notes(patterns: Any | None) -> list[str]:
    if patterns is None or int(getattr(patterns, "tracked_days", 0) or 0) < 5:
        return [
            "Паттерны: пока мало истории. Через несколько "
            "дней записей "
            "бот начнёт замечать повторяющиеся сценарии."
        ]

    tracked_days = int(patterns.tracked_days)
    notes: list[str] = []

    no_breakfast_days = int(patterns.no_breakfast_days)
    no_breakfast_over_target_days = int(patterns.no_breakfast_over_target_days)
    if no_breakfast_days >= 2:
        ratio = no_breakfast_over_target_days / no_breakfast_days
        if ratio >= 0.5:
            notes.append(
                "Паттерн: в дни без завтрака вечером чаще тянет добрать лишнее. "
                "Лучше занести хотя бы лёгкий белковый завтрак."
            )

    sweet_drink_days = int(patterns.sweet_drink_days)
    sweet_drink_delta = float(patterns.sweet_drink_average_delta)
    if sweet_drink_days >= 2 and sweet_drink_delta >= 150:
        notes.append(
            "Паттерн: в дни со сладкими напитками "
            "калорийность выше "
            f"примерно на {sweet_drink_delta:.0f} ккал."
        )

    usual_evening_kcal = float(patterns.average_evening_kcal)
    if usual_evening_kcal >= 600:
        notes.append(
            "Паттерн: вечером обычно набирается много "
            "калорий "
            f"(около {usual_evening_kcal:.0f}). Обед лучше держать легче."
        )

    if notes:
        return notes
    return [
        f"Паттерны: за {tracked_days} дней явных "
        "повторяющихся перекосов "
        "не видно. Продолжаем собирать историю."
    ]


def smart_morning_hint(yesterday: DiarySummary) -> str:
    if not yesterday.entries:
        return "Вчера дневник пустой. Сегодня проще начать с завтрака и пары быстрых записей."

    kcal_delta = yesterday.kcal - yesterday.target_kcal
    protein_left = yesterday.target_protein - yesterday.protein
    if kcal_delta > 200:
        return (
            "Вчера калории были выше цели. "
            "Сегодня начни спокойно: белок, вода и обычный ритм без наказаний."
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
        f"{detail}. Если это реальная еда, добавим спокойно. Точно добавить?"
    )

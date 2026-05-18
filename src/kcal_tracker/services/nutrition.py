from __future__ import annotations

from kcal_tracker.schemas import DiarySummary


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

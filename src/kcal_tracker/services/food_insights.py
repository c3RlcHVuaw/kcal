from __future__ import annotations

from kcal_tracker.schemas import FoodEstimate

DEFAULT_EMOJI = "🍽️"

EMOJI_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("кофе", "☕"),
    ("капучино", "☕"),
    ("латте", "☕"),
    ("чай", "🍵"),
    ("вода", "💧"),
    ("банан", "🍌"),
    ("яблок", "🍎"),
    ("груш", "🍐"),
    ("апельсин", "🍊"),
    ("мандарин", "🍊"),
    ("ягод", "🫐"),
    ("клубник", "🍓"),
    ("виноград", "🍇"),
    ("авокад", "🥑"),
    ("салат", "🥗"),
    ("овощ", "🥗"),
    ("огур", "🥒"),
    ("помид", "🍅"),
    ("морков", "🥕"),
    ("карто", "🥔"),
    ("суп", "🍲"),
    ("борщ", "🍲"),
    ("каша", "🥣"),
    ("овсян", "🥣"),
    ("греч", "🥣"),
    ("рис", "🍚"),
    ("паста", "🍝"),
    ("макарон", "🍝"),
    ("лапш", "🍜"),
    ("хлеб", "🍞"),
    ("тост", "🍞"),
    ("сыр", "🧀"),
    ("йогурт", "🥛"),
    ("творог", "🥛"),
    ("молок", "🥛"),
    ("яйц", "🥚"),
    ("куриц", "🍗"),
    ("индейк", "🍗"),
    ("мяс", "🥩"),
    ("говя", "🥩"),
    ("свинин", "🥩"),
    ("рыб", "🐟"),
    ("лосос", "🐟"),
    ("тунец", "🐟"),
    ("кревет", "🍤"),
    ("бургер", "🍔"),
    ("пицц", "🍕"),
    ("шаур", "🌯"),
    ("ролл", "🌯"),
    ("тако", "🌮"),
    ("шоколад", "🍫"),
    ("конфет", "🍬"),
    ("печень", "🍪"),
    ("торт", "🍰"),
    ("пирож", "🍰"),
    ("морож", "🍦"),
    ("пончик", "🍩"),
    ("сок", "🧃"),
)

SWEET_TERMS = (
    "сахар",
    "слад",
    "шоколад",
    "конфет",
    "печень",
    "торт",
    "пирож",
    "морож",
    "пончик",
    "десерт",
    "сироп",
    "варенье",
    "мед",
    "газиров",
    "кола",
    "сок",
)
FRIED_TERMS = ("жарен", "фри", "наггет", "чипс")
PROCESSED_TERMS = ("колбас", "сосиск", "бекон", "ветчин")
FRUIT_VEG_TERMS = (
    "яблок",
    "банан",
    "груш",
    "апельсин",
    "ягод",
    "овощ",
    "салат",
    "огур",
    "помид",
    "морков",
)


def enrich_food_payload[FoodPayload: FoodEstimate](payload: FoodPayload) -> FoodPayload:
    data = payload.model_dump()
    data["emoji"] = normalize_emoji(payload.emoji) or food_emoji(payload.name)
    data["advice"] = normalize_advice(payload.advice) or food_advice(
        payload.name,
        kcal=payload.kcal,
        protein=payload.protein,
        fat=payload.fat,
        carbs=payload.carbs,
    )
    return payload.__class__(**data)


def food_label(item) -> str:
    name = getattr(item, "name", None) or getattr(item, "food_name", "Еда")
    emoji = normalize_emoji(getattr(item, "emoji", None)) or food_emoji(name)
    return f"{emoji} {name}"


def food_emoji(name: str) -> str:
    lowered = name.casefold()
    for keyword, emoji in EMOJI_KEYWORDS:
        if keyword in lowered:
            return emoji
    return DEFAULT_EMOJI


def food_advice(name: str, kcal: float, protein: float, fat: float, carbs: float) -> str:
    lowered = name.casefold()
    if any(term in lowered for term in SWEET_TERMS):
        return (
            "Сладкое лучше оставлять небольшой порцией: "
            "избыток сахара может усиливать тягу к перекусам "
            "и у части людей отражаться на коже."
        )
    if any(term in lowered for term in FRIED_TERMS):
        return (
            "Жареное легко разгоняет калории и жиры; "
            "в следующий приём пищи добавь воды и овощей."
        )
    if any(term in lowered for term in PROCESSED_TERMS):
        return (
            "В переработанном мясе часто много соли и насыщенных жиров; "
            "лучше не делать его базой дня."
        )
    if any(term in lowered for term in FRUIT_VEG_TERMS):
        return (
            "Хороший источник клетчатки. "
            "Для сытости можно добавить белок: йогурт, яйца или творог."
        )
    if protein >= 20 and kcal <= 500:
        return (
            "Белка здесь прилично, "
            "это помогает сытости и восстановлению."
        )
    if kcal >= 700:
        return (
            "Порция калорийная; "
            "дальше по дню лучше выбирать более лёгкие блюда."
        )
    if carbs >= 70 and protein < 10:
        return (
            "Много углеводов и мало белка; "
            "белковое дополнение поможет дольше оставаться сытым."
        )
    if fat >= 35:
        return (
            "Жиров много для одной позиции; "
            "овощи или крупа без масла помогут сбалансировать день."
        )
    return (
        "Нормальная позиция для дневника; "
        "ориентируйся на общий итог калорий и БЖУ за день."
    )


def normalize_emoji(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    return value[:16] if value else None


def normalize_advice(value: str | None) -> str | None:
    if not value:
        return None
    value = " ".join(value.strip().split())
    if not value:
        return None
    return value[:255]

from __future__ import annotations

import re
from dataclasses import dataclass

from kcal_tracker.schemas import FoodEstimate
from kcal_tracker.services.food_insights import enrich_food_payload


@dataclass(frozen=True)
class FoodNutrition:
    name: str
    kcal_100g: float
    protein_100g: float = 0
    fat_100g: float = 0
    carbs_100g: float = 0


COMMON_FOODS: dict[str, FoodNutrition] = {
    "яблоко": FoodNutrition("яблоко", 52, 0.3, 0.2, 14),
    "банан": FoodNutrition("банан", 89, 1.1, 0.3, 23),
    "апельсин": FoodNutrition("апельсин", 47, 0.9, 0.1, 12),
    "огурец": FoodNutrition("огурец", 15, 0.7, 0.1, 3.6),
    "помидор": FoodNutrition("помидор", 18, 0.9, 0.2, 3.9),
    "картофель": FoodNutrition("картофель", 77, 2, 0.1, 17),
    "рис": FoodNutrition("рис варёный", 130, 2.7, 0.3, 28),
    "гречка": FoodNutrition("гречка варёная", 110, 3.6, 1.1, 20),
    "овсянка": FoodNutrition("овсянка варёная", 71, 2.5, 1.5, 12),
    "макароны": FoodNutrition("макароны варёные", 158, 5.8, 0.9, 31),
    "курица": FoodNutrition("курица", 165, 31, 3.6, 0),
    "куриная грудка": FoodNutrition("куриная грудка", 165, 31, 3.6, 0),
    "говядина": FoodNutrition("говядина", 187, 19, 12, 0),
    "свинина": FoodNutrition("свинина", 242, 27, 14, 0),
    "лосось": FoodNutrition("лосось", 208, 20, 13, 0),
    "яйцо": FoodNutrition("яйцо", 155, 13, 11, 1.1),
    "творог": FoodNutrition("творог 5%", 121, 17, 5, 3),
    "кефир": FoodNutrition("кефир", 53, 3, 2.5, 4),
    "молоко": FoodNutrition("молоко", 60, 3, 3.2, 4.7),
    "коктейль молочный": FoodNutrition("молочный коктейль", 85, 3, 2, 14),
    "молочный коктейль": FoodNutrition("молочный коктейль", 85, 3, 2, 14),
    "протеиновый коктейль": FoodNutrition("протеиновый коктейль", 75, 8, 2, 6),
    "латте": FoodNutrition("латте", 55, 3, 2, 5),
    "сыр": FoodNutrition("сыр", 350, 25, 27, 2),
    "хлеб": FoodNutrition("хлеб", 250, 8, 3, 49),
    "пицца": FoodNutrition("пицца", 260, 11, 10, 32),
    "чизкейк": FoodNutrition("чизкейк", 321, 6, 22, 26),
    "пастила": FoodNutrition("пастила", 320, 0.5, 0.2, 80),
    "яблочная пастила": FoodNutrition("яблочная пастила", 276, 1, 0.5, 68),
    "батончик": FoodNutrition("батончик", 430, 6, 18, 62),
    "батончик мюсли": FoodNutrition("батончик мюсли", 370, 6, 8, 65),
    "протеиновый батончик": FoodNutrition("протеиновый батончик", 330, 30, 10, 28),
    "батончик протеиновый": FoodNutrition("протеиновый батончик", 330, 30, 10, 28),
    "шоколадный батончик": FoodNutrition("шоколадный батончик", 500, 6, 28, 60),
}


def estimate_common_food(text: str) -> FoodEstimate | None:
    normalized = _normalize(text)
    if not normalized:
        return None

    grams = _extract_grams(normalized) or 100
    nutrition = _find_food(normalized)
    if nutrition is None:
        return None

    ratio = grams / 100
    return enrich_food_payload(
        FoodEstimate(
            name=nutrition.name,
            weight_g=grams,
            kcal=round(nutrition.kcal_100g * ratio, 1),
            protein=round(nutrition.protein_100g * ratio, 1),
            fat=round(nutrition.fat_100g * ratio, 1),
            carbs=round(nutrition.carbs_100g * ratio, 1),
            confidence=0.75,
        )
    )


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace(",", ".").split())


def _extract_grams(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:г|гр|грамм|g)\b", text)
    if not match:
        return None
    value = float(match.group(1))
    if 0 < value <= 5000:
        return value
    return None


def _find_food(text: str) -> FoodNutrition | None:
    for key in sorted(COMMON_FOODS, key=len, reverse=True):
        pattern = rf"(?<![a-zа-яё0-9]){re.escape(key)}(?![a-zа-яё0-9])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return COMMON_FOODS[key]
    return None

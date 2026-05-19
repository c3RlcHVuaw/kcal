from __future__ import annotations

import base64
import json

from openai import AsyncOpenAI

from kcal_tracker.config import settings
from kcal_tracker.schemas import FoodEstimate, FoodEstimateList
from kcal_tracker.services.food_insights import enrich_food_payload

FOOD_RECOGNITION_PROMPT = """Распознай еду на фото.

Верни только строгий JSON такого вида:
{
  "foods": [
    {
      "name": "название блюда или продукта на русском",
      "weight_g": 123,
      "kcal": 456,
      "protein": 12,
      "fat": 10,
      "carbs": 45,
      "confidence": 0.72,
      "emoji": "🍌",
      "advice": "короткий полезный совет по этому продукту на русском"
    }
  ]
}

Правила:
- Все названия в поле name пиши по-русски: "латте", "гречка с курицей", "банан".
- Если видно несколько продуктов, верни каждый отдельной позицией.
- Если пользователь дал текстовое уточнение к фото, обязательно учти его:
  граммовку, состав, соусы, скрытые продукты, половину/часть порции и любые исправления.
- Используй реалистичные приблизительные граммы, калории и БЖУ.
- Для каждой позиции подбери один подходящий emoji.
- Для каждой позиции дай короткий отдельный advice: польза, риск или как сбалансировать продукт.
- Если продукт сладкий, жирный, солёный или очень калорийный, мягко предупреди об этом.
- Никогда не возвращай confidence 1.0.
- Если сомневаешься, снизь confidence.
- Если фото не подходит для распознавания еды, верни {"foods":[]}.
"""

TEXT_PARSE_PROMPT = """Разбери описание еды пользователя.

Верни только строгий JSON такого вида:
{
  "foods": [
    {
      "name": "название блюда или продукта на русском",
      "weight_g": 123,
      "kcal": 456,
      "protein": 12,
      "fat": 10,
      "carbs": 45,
      "confidence": 0.72,
      "emoji": "🍌",
      "advice": "короткий полезный совет по этому продукту на русском"
    }
  ]
}

Правила:
- Все названия в поле name пиши по-русски.
- Если пользователь перечислил несколько продуктов, верни каждый отдельной позицией.
- Оцени калории и БЖУ спокойно и консервативно.
- Для каждой позиции подбери один подходящий emoji.
- Для каждой позиции дай короткий отдельный advice: польза, риск или как сбалансировать продукт.
- Если продукт сладкий, жирный, солёный или очень калорийный, мягко предупреди об этом.
- Никогда не возвращай confidence 1.0.
"""


class AIFoodService:
    def __init__(self) -> None:
        self.client = (
            AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )

    async def recognize_photo(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        text_hint: str | None = None,
    ) -> FoodEstimateList:
        if self.client is None:
            return FoodEstimateList(foods=[])

        encoded = base64.b64encode(image_bytes).decode("ascii")
        response = await self.client.chat.completions.create(
            model=settings.openai_vision_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": FOOD_RECOGNITION_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": photo_recognition_user_text(text_hint),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                        },
                    ],
                },
            ],
            temperature=0.2,
            timeout=20,
        )
        return self._parse_foods(response.choices[0].message.content)

    async def parse_text(self, text: str) -> FoodEstimateList:
        if self.client is None:
            return FoodEstimateList(foods=[])

        response = await self.client.chat.completions.create(
            model=settings.openai_text_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": TEXT_PARSE_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            timeout=12,
        )
        return self._parse_foods(response.choices[0].message.content)

    def _parse_foods(self, content: str | None) -> FoodEstimateList:
        if not content:
            return FoodEstimateList(foods=[])
        data = json.loads(content)
        foods = []
        for item in data.get("foods", []):
            confidence = item.get("confidence")
            if confidence is not None:
                confidence = min(float(confidence), 0.99)
            foods.append(
                enrich_food_payload(
                    FoodEstimate(
                        name=item.get("name") or "Еда",
                        weight_g=item.get("weight_g") or item.get("estimated_weight_g"),
                        kcal=item.get("kcal") or item.get("estimated_kcal") or 0,
                        protein=item.get("protein") or 0,
                        fat=item.get("fat") or 0,
                        carbs=item.get("carbs") or 0,
                        confidence=confidence,
                        emoji=item.get("emoji"),
                        advice=item.get("advice"),
                    )
                )
            )
        return FoodEstimateList(foods=foods)


def photo_recognition_user_text(text_hint: str | None = None) -> str:
    base = "Оцени еду на фото. Названия продуктов верни на русском."
    hint = normalize_photo_text_hint(text_hint)
    if not hint:
        return base
    return (
        f"{base}\n\n"
        "Уточнение пользователя к фото, его нужно учесть при оценке:\n"
        f"{hint}"
    )


def normalize_photo_text_hint(text_hint: str | None) -> str | None:
    if not text_hint:
        return None
    hint = " ".join(text_hint.strip().split())
    return hint[:500] if hint else None

from __future__ import annotations

import base64
import json

from openai import AsyncOpenAI

from kcal_tracker.config import settings
from kcal_tracker.schemas import FoodEstimate, FoodEstimateList

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
      "confidence": 0.72
    }
  ]
}

Правила:
- Все названия в поле name пиши по-русски: "латте", "гречка с курицей", "банан".
- Если видно несколько продуктов, верни каждый отдельной позицией.
- Используй реалистичные приблизительные граммы, калории и БЖУ.
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
      "confidence": 0.72
    }
  ]
}

Правила:
- Все названия в поле name пиши по-русски.
- Если пользователь перечислил несколько продуктов, верни каждый отдельной позицией.
- Оцени калории и БЖУ спокойно и консервативно.
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
                            "text": "Оцени еду на фото. Названия продуктов верни на русском.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                        },
                    ],
                },
            ],
            temperature=0.2,
            timeout=4,
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
            timeout=4,
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
                FoodEstimate(
                    name=item.get("name") or "Еда",
                    weight_g=item.get("weight_g") or item.get("estimated_weight_g"),
                    kcal=item.get("kcal") or item.get("estimated_kcal") or 0,
                    protein=item.get("protein") or 0,
                    fat=item.get("fat") or 0,
                    carbs=item.get("carbs") or 0,
                    confidence=confidence,
                )
            )
        return FoodEstimateList(foods=foods)

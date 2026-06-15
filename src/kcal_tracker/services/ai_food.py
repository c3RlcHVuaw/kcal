from __future__ import annotations

import base64
import json

from openai import AsyncOpenAI

from kcal_tracker.config import settings
from kcal_tracker.schemas import FoodEstimate, FoodEstimateList
from kcal_tracker.services.food_insights import enrich_food_payload

FOOD_RECOGNITION_PROMPT = """Распознай только еду, которая явно видна на фото.

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
      "advice": "короткий полезный совет по этому продукту на русском",
      "packaged": true
    }
  ]
}

Жёсткие правила видимости:
- Возвращай только съедобные объекты, которые реально видны на фото или прямо названы пользователем в уточнении.
- Не добавляй типичные продукты из контекста, завтрак-комбо, гарниры, напитки, фрукты, кашу, кофе или соусы,
  если их не видно и пользователь их не упомянул.
- Не считай аксессуары, упаковку, текст на упаковке, фон, стол, технику, чехлы, провода и другие предметы едой.
- Если на фото один упакованный продукт или один предмет еды, верни ровно одну позицию.
- Если продукт в упаковке с читаемым названием, используй видимое название/тип продукта, а не придумывай соседние блюда.
- Для каждой позиции укажи packaged=true, только если видна упаковка, этикетка, бренд или штрихкод; иначе packaged=false.
- Если не уверен, что второй объект является едой, не возвращай его.
- Если видно несколько отдельных продуктов на тарелке/столе, верни каждый отдельной позицией.

Общие правила:
- Все названия в поле name пиши по-русски: "шоколадный маффин", "гречка с курицей", "банан".
- Если пользователь дал текстовое уточнение к фото, обязательно учти его:
  граммовку, состав, соусы, скрытые продукты, половину/часть порции и любые исправления.
- Если на фото видна не вся тарелка или пользователь указал долю порции,
  оцени только съедаемую/видимую часть, а не стандартную ресторанную порцию.
- Отдельно учитывай масло, соусы, сыр, сахар, джем, напитки и гарниры,
  если они видны или упомянуты пользователем.
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

FOOD_REFINEMENT_PROMPT = """Уточни уже распознанную оценку еды по новому комментарию пользователя.

Верни только строгий JSON такого вида:
{
  "foods": [
    {
      "name": "уточнённое название блюда или продукта на русском",
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
- Верни ровно одну уточнённую позицию.
- Обязательно учти комментарий пользователя: добавки, соусы, джем, масло,
  скрытые ингредиенты, частичную порцию, исправления веса или состава.
- Если пользователь добавил ингредиент к блюду, пересчитай итоговые граммы, калории и БЖУ.
- Все названия в поле name пиши по-русски.
- Для позиции подбери один подходящий emoji и короткий advice.
- Никогда не возвращай confidence 1.0.
"""

FOOD_SPLIT_PROMPT = """Разбей сложное блюдо на понятные части.

Верни только строгий JSON такого вида:
{
  "foods": [
    {
      "name": "ингредиент или часть блюда на русском",
      "weight_g": 123,
      "kcal": 456,
      "protein": 12,
      "fat": 10,
      "carbs": 45,
      "confidence": 0.72,
      "emoji": "🍗",
      "advice": "короткий полезный совет"
    }
  ]
}

Правила:
- Разбивай только реальное сложное блюдо: шаурма, паста, салат, суп, пицца,
  бургер, роллы, плов, каша с добавками, мясо с гарниром.
- Если это одиночный продукт или брендовый батончик, верни исходную позицию одной строкой.
- Суммарные калории и граммы должны быть близки к исходной оценке.
- Отдельно выделяй соус, масло, сыр, сладкие добавки, гарнир и белковую часть.
- Все названия пиши по-русски.
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
        return await self.recognize_photos([(image_bytes, mime_type)], text_hint=text_hint)

    async def recognize_photos(
        self,
        images: list[tuple[bytes, str]],
        text_hint: str | None = None,
    ) -> FoodEstimateList:
        if self.client is None:
            return FoodEstimateList(foods=[])

        content = [
            {
                "type": "text",
                "text": photo_recognition_user_text(text_hint, photo_count=len(images)),
            }
        ]
        for image_bytes, mime_type in images[:6]:
            encoded = base64.b64encode(image_bytes).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                }
            )
        response = await self.client.chat.completions.create(
            model=settings.openai_vision_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": FOOD_RECOGNITION_PROMPT},
                {
                    "role": "user",
                    "content": content,
                },
            ],
            temperature=0.2,
            timeout=20,
        )
        return self._parse_foods(
            response.choices[0].message.content,
            strict_visible_single=len(images) == 1 and not normalize_photo_text_hint(text_hint),
        )

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

    async def refine_estimate(
        self,
        estimate: FoodEstimate,
        refinement: str,
    ) -> FoodEstimateList:
        if self.client is None:
            return FoodEstimateList(foods=[])

        response = await self.client.chat.completions.create(
            model=settings.openai_text_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": FOOD_REFINEMENT_PROMPT},
                {"role": "user", "content": food_refinement_user_text(estimate, refinement)},
            ],
            temperature=0.2,
            timeout=12,
        )
        return self._parse_foods(response.choices[0].message.content)

    async def split_estimate(self, estimate: FoodEstimate) -> FoodEstimateList:
        if self.client is None:
            return FoodEstimateList(foods=[])

        response = await self.client.chat.completions.create(
            model=settings.openai_text_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": FOOD_SPLIT_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Исходная оценка блюда, которую нужно разложить на части:\n"
                        f"{estimate.model_dump_json()}"
                    ),
                },
            ],
            temperature=0.2,
            timeout=12,
        )
        return self._parse_foods(response.choices[0].message.content)

    def _parse_foods(
        self,
        content: str | None,
        *,
        strict_visible_single: bool = False,
    ) -> FoodEstimateList:
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
                        packaged=item.get("packaged"),
                    )
                )
            )
        if strict_visible_single:
            foods = limit_visible_photo_foods(foods)
        return FoodEstimateList(foods=foods)


def photo_recognition_user_text(text_hint: str | None = None, *, photo_count: int = 1) -> str:
    base = (
        "Оцени только явно видимую еду на фото. "
        "Не добавляй продукты, которых не видно. "
        "Если видна упаковка, этикетка или бренд, сначала прочитай реальное название "
        "и верни именно его; не придумывай похожий продукт."
    )
    if photo_count > 1:
        base += f" Пользователь прислал {photo_count} фото; объедини все явно видимые продукты."
    hint = normalize_photo_text_hint(text_hint)
    if not hint:
        return base
    return (
        f"{base}\n\n"
        "Уточнение пользователя к фото, его нужно учесть при оценке:\n"
        f"{hint}"
    )


def food_refinement_user_text(estimate: FoodEstimate, refinement: str) -> str:
    hint = normalize_photo_text_hint(refinement) or refinement.strip()
    return (
        "Текущая оценка еды:\n"
        f"{estimate.model_dump_json()}\n\n"
        "Новое уточнение пользователя, которое нужно учесть:\n"
        f"{hint}"
    )


def normalize_photo_text_hint(text_hint: str | None) -> str | None:
    if not text_hint:
        return None
    hint = " ".join(text_hint.strip().split())
    return hint[:500] if hint else None


def limit_visible_photo_foods(foods: list[FoodEstimate]) -> list[FoodEstimate]:
    if len(foods) <= 1:
        return foods

    ranked = sorted(
        foods,
        key=lambda food: (
            food.confidence or 0,
            food.kcal or 0,
            food.weight_g or 0,
        ),
        reverse=True,
    )
    top = ranked[0]
    second = ranked[1]

    if len(foods) > 2:
        return [top]
    if (top.confidence or 0) >= 0.6 and (second.confidence or 0) <= (top.confidence or 0) - 0.12:
        return [top]
    if (top.kcal or 0) >= max((second.kcal or 0) * 1.8, 180):
        return [top]
    return ranked[:2]

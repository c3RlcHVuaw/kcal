from __future__ import annotations

import json

from openai import AsyncOpenAI

from kcal_tracker.config import settings
from kcal_tracker.schemas import ActivityEstimate

ACTIVITY_PARSE_PROMPT = """Разбери описание активности пользователя.

Верни только строгий JSON такого вида:
{
  "name": "название активности на русском",
  "kcal": 180,
  "confidence": 0.72
}

Правила:
- Если пользователь прямо написал потраченные калории, используй это число.
- Если пользователь описал активность без калорий, оцени расход спокойно и консервативно.
- Если активности нет или оценить нельзя, верни {"name":"", "kcal":0, "confidence":0}.
- Никогда не возвращай confidence 1.0.
"""


class AIActivityService:
    def __init__(self) -> None:
        self.client = (
            AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )

    async def parse_text(self, text: str) -> ActivityEstimate | None:
        if self.client is None:
            return None

        response = await self.client.chat.completions.create(
            model=settings.openai_text_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": ACTIVITY_PARSE_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            timeout=4,
        )
        return self._parse_activity(response.choices[0].message.content)

    def _parse_activity(self, content: str | None) -> ActivityEstimate | None:
        if not content:
            return None
        data = json.loads(content)
        kcal = float(data.get("kcal") or data.get("estimated_kcal") or 0)
        name = str(data.get("name") or data.get("activity") or "").strip()
        if not name or kcal <= 0:
            return None
        confidence = data.get("confidence")
        if confidence is not None:
            confidence = min(float(confidence), 0.99)
        return ActivityEstimate(name=name, kcal=kcal, confidence=confidence)

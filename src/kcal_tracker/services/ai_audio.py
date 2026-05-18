from __future__ import annotations

import httpx

from kcal_tracker.config import settings


class AIAudioService:
    async def transcribe(self, audio_bytes: bytes) -> str:
        if not settings.openai_api_key:
            return ""

        files = {"file": ("voice.mp3", audio_bytes, "audio/mpeg")}
        data = {
            "model": settings.openai_transcribe_model,
            "response_format": "json",
        }
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                data=data,
                files=files,
            )
            response.raise_for_status()
        return response.json().get("text", "").strip()

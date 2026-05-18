from __future__ import annotations

import re

ACTIVITY_WORDS = (
    "актив",
    "бег",
    "бежал",
    "бежала",
    "велосипед",
    "зал",
    "трен",
    "ходьб",
    "шаг",
    "плав",
    "потрат",
    "сжег",
    "сжёг",
    "сожг",
)


def parse_int_from_text(text: str, minimum: int, maximum: int) -> int | None:
    match = re.search(r"\d+", text)
    if not match:
        return None
    try:
        value = int(match.group())
    except ValueError:
        return None
    return value if minimum <= value <= maximum else None


def looks_like_activity(text: str) -> bool:
    normalized = text.strip().casefold()
    return any(word in normalized for word in ACTIVITY_WORDS)


def parse_activity_kcal(text: str, allow_plain_kcal: bool = False) -> int | None:
    normalized = text.casefold().replace("ё", "е")
    if not allow_plain_kcal and not looks_like_activity(normalized):
        return None

    patterns = [
        r"(?:потрат\w*|сжег\w*|сожг\w*)\D{0,20}(\d{1,4})",
        r"(\d{1,4})\s*(?:ккал|калор)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            value = int(match.group(1))
            return value if 1 <= value <= 5000 else None
    return None

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from statistics import pstdev

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError


@dataclass(frozen=True)
class PhotoQualityIssue:
    reason: str
    user_text: str


def detect_photo_quality_issue(image_bytes: bytes) -> PhotoQualityIssue | None:
    if len(image_bytes) < 2_000:
        return PhotoQualityIssue(
            "small_file",
            "Фото слишком маленькое или сильно сжато. Лучше отправь снимок ближе и без обрезки.",
        )
    try:
        image = Image.open(BytesIO(image_bytes)).convert("L")
    except (UnidentifiedImageError, OSError):
        return PhotoQualityIssue(
            "unreadable",
            "Не смог прочитать фото. Отправь изображение ещё раз или попробуй другой снимок.",
        )

    width, height = image.size
    if width < 320 or height < 320:
        return PhotoQualityIssue(
            "low_resolution",
            "Фото слишком маленькое. Лучше сфоткай еду ближе, чтобы были видны детали.",
        )

    thumbnail = image.resize((160, 160))
    stat = ImageStat.Stat(thumbnail)
    brightness = float(stat.mean[0])
    contrast = float(stat.stddev[0])
    sharpness = _edge_sharpness(thumbnail)

    if brightness < 35:
        return PhotoQualityIssue(
            "too_dark",
            "Фото слишком тёмное, могу ошибиться. Лучше сделай снимок при свете или включи вспышку.",
        )
    if contrast < 12:
        return PhotoQualityIssue(
            "low_contrast",
            "Еда плохо отделяется от фона. Лучше сфоткай ближе и без бликов.",
        )
    if sharpness < 7:
        return PhotoQualityIssue(
            "blurry",
            "Фото выглядит смазанным. Лучше переснять так, чтобы еда или этикетка были резкими.",
        )
    return None


def _edge_sharpness(image: Image.Image) -> float:
    edges = image.filter(ImageFilter.FIND_EDGES)
    values = list(edges.getdata())
    return pstdev(values) if values else 0.0

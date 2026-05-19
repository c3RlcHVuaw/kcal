from __future__ import annotations

from collections.abc import Iterable
from io import BytesIO

from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError


class BarcodeNotFoundError(RuntimeError):
    pass


class BarcodeService:
    async def decode_image(self, image_bytes: bytes) -> str:
        try:
            image = Image.open(BytesIO(image_bytes))
            image = ImageOps.exif_transpose(image).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise BarcodeNotFoundError("Image could not be opened") from exc

        for candidate in _barcode_candidates(image):
            value = _decode_first(candidate)
            if value is not None:
                return value

        raise BarcodeNotFoundError("Barcode not found")


def _decode_first(image: Image.Image) -> str | None:
    from pyzbar.pyzbar import decode

    for code in decode(image):
        try:
            value = code.data.decode("utf-8").strip()
        except UnicodeDecodeError:
            continue
        if value:
            return value
    return None


def _barcode_candidates(image: Image.Image) -> Iterable[Image.Image]:
    base_images = [image, *_central_crops(image), *_grid_crops(image)]
    for base in base_images:
        for rotated in _rotations(base):
            yield rotated
            enhanced = _enhance_for_barcode(rotated)
            yield enhanced
            yield _upscale(enhanced, factor=2)

            grayscale = ImageOps.grayscale(enhanced)
            yield grayscale
            yield ImageOps.autocontrast(grayscale)
            yield ImageOps.equalize(grayscale)
            yield ImageOps.invert(ImageOps.autocontrast(grayscale))
            for threshold in (96, 128, 160):
                yield grayscale.point(
                    lambda pixel, t=threshold: 255 if pixel > t else 0,
                    mode="1",
                )


def _central_crops(image: Image.Image) -> list[Image.Image]:
    width, height = image.size
    if width < 80 or height < 80:
        return []

    crops = []
    for ratio in (0.9, 0.78):
        crop_width = int(width * ratio)
        crop_height = int(height * ratio)
        left = (width - crop_width) // 2
        top = (height - crop_height) // 2
        crops.append(image.crop((left, top, left + crop_width, top + crop_height)))
    return crops


def _grid_crops(image: Image.Image) -> list[Image.Image]:
    width, height = image.size
    if width < 240 or height < 240:
        return []

    crops = []
    for crop_ratio in (0.62, 0.5):
        crop_width = int(width * crop_ratio)
        crop_height = int(height * crop_ratio)
        if crop_width < 120 or crop_height < 120:
            continue
        for x_ratio, y_ratio in (
            (0.25, 0.25),
            (0.75, 0.25),
            (0.25, 0.75),
            (0.75, 0.75),
            (0.5, 0.25),
            (0.5, 0.75),
        ):
            center_x = int(width * x_ratio)
            center_y = int(height * y_ratio)
            left = min(max(center_x - crop_width // 2, 0), width - crop_width)
            top = min(max(center_y - crop_height // 2, 0), height - crop_height)
            crops.append(image.crop((left, top, left + crop_width, top + crop_height)))
    return crops


def _rotations(image: Image.Image) -> Iterable[Image.Image]:
    yield image
    for angle in (-8, -4, 4, 8, 90, 180, 270):
        yield image.rotate(angle, expand=True, fillcolor="white")


def _enhance_for_barcode(image: Image.Image) -> Image.Image:
    enhanced = ImageOps.autocontrast(image)
    enhanced = ImageEnhance.Contrast(enhanced).enhance(1.8)
    enhanced = ImageEnhance.Sharpness(enhanced).enhance(2.0)
    return enhanced.filter(ImageFilter.SHARPEN)


def _upscale(image: Image.Image, factor: int) -> Image.Image:
    width, height = image.size
    if max(width, height) >= 2400:
        return image
    return image.resize((width * factor, height * factor), Image.Resampling.LANCZOS)

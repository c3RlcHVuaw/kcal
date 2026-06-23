from __future__ import annotations

from io import BytesIO

from PIL import Image

from kcal_tracker.bot.handlers.food import (
    _filter_relevant_estimates,
    _is_confident_single_search_match,
)
from kcal_tracker.schemas import FoodEntryCreate, FoodEstimate
from kcal_tracker.services.brand_lookup import (
    _best_brand_match,
    _brand_lookup_queries,
    mark_unverified_packaged_estimate,
)
from kcal_tracker.services.catalog_import import read_catalog_seed
from kcal_tracker.services.food_catalog import (
    _can_learn,
    _score_text_match,
    normalize_food_text,
    scale_estimate,
)
from kcal_tracker.services.food_search import estimate_common_food
from kcal_tracker.services.photo_quality import detect_photo_quality_issue


def test_estimate_common_food_handles_milkshake_ocr_text() -> None:
    estimate = estimate_common_food(
        "КОКТЕЙЛЬ МОЛОЧНЫЙ ПАСТЕРИЗОВАННЫЙ СО ВКУСОМ ЛЕСНОГО ОРЕХА "
        "И КОФЕ ОРЕХОВЫЙ ЛАТТЕ"
    )

    assert estimate is not None
    assert estimate.name == "молочный коктейль"
    assert estimate.kcal == 85


def test_estimate_common_food_does_not_match_inside_words() -> None:
    assert estimate_common_food("ириска 50 г") is None
    assert estimate_common_food("сырники 150 г") is None


def test_estimate_common_food_handles_pastila() -> None:
    estimate = estimate_common_food("Пастила 50 г")

    assert estimate is not None
    assert estimate.name == "пастила"
    assert estimate.weight_g == 50
    assert estimate.kcal == 160


def test_estimate_common_food_handles_bar_variants() -> None:
    estimate = estimate_common_food("протеиновый батончик 60 г")

    assert estimate is not None
    assert estimate.name == "протеиновый батончик"
    assert estimate.weight_g == 60
    assert estimate.protein == 18


def test_food_search_filters_irrelevant_database_results() -> None:
    estimates = [
        FoodEstimate(name="картофельное пюре", kcal=120, confidence=0.75),
        FoodEstimate(name="ореховый латте", kcal=160, confidence=0.75),
    ]

    filtered = _filter_relevant_estimates("латте 300 мл", estimates, limit=5)

    assert [estimate.name for estimate in filtered] == ["ореховый латте"]


def test_single_database_result_needs_confident_match() -> None:
    estimate = FoodEstimate(name="ореховый латте", kcal=160, confidence=0.5)

    assert not _is_confident_single_search_match("латте 300 мл", estimate)
    assert _is_confident_single_search_match("латте", estimate)


def test_brand_lookup_prefers_real_packaged_product_match() -> None:
    ai_estimate = FoodEstimate(
        name="протеиновый батончик фисташка",
        kcal=210,
        visible_brand="Bombbar",
        visible_label_text="Bombbar фисташковая меренга 60 г",
    )
    candidates = [
        FoodEstimate(name="обычный шоколадный батончик", kcal=520),
        FoodEstimate(name="Bombbar протеиновый батончик фисташковая меренга", kcal=300),
    ]

    matched = _best_brand_match(ai_estimate, candidates)

    assert matched is not None
    assert matched.name == "Bombbar протеиновый батончик фисташковая меренга"


def test_brand_lookup_queries_prefer_visible_label_text() -> None:
    estimate = FoodEstimate(
        name="упакованный протеиновый батончик",
        kcal=210,
        packaged=True,
        visible_brand="Bombbar",
        visible_label_text="Bombbar фисташковая меренга 60 г",
    )

    assert _brand_lookup_queries(estimate)[:2] == [
        "Bombbar фисташковая меренга 60 г",
        "Bombbar упакованный протеиновый батончик",
    ]


def test_packaged_ai_estimate_is_marked_unverified_without_database_match() -> None:
    estimate = FoodEstimate(
        name="Bombbar похожий батончик",
        kcal=210,
        confidence=0.82,
        packaged=True,
    )

    marked = mark_unverified_packaged_estimate(estimate)

    assert marked.source_label == "Проверь бренд"
    assert marked.is_ai_suggestion is True
    assert marked.packaged is True
    assert marked.confidence == 0.55
    assert marked.advice is not None
    assert "Проверь бренд" in marked.advice


def test_unverified_packaged_estimate_does_not_use_technical_name() -> None:
    estimate = FoodEstimate(
        name="упакованный продукт, бренд не читается",
        kcal=350,
        confidence=0.42,
        packaged=True,
        visible_label_text="творожная запеканка",
    )

    marked = mark_unverified_packaged_estimate(estimate)

    assert marked.name == "творожная запеканка"
    assert "бренд не читается" not in marked.name


def test_photo_quality_detects_too_dark_photo() -> None:
    issue = detect_photo_quality_issue(_jpeg_bytes((420, 420), color=8))

    assert issue is not None
    assert issue.reason == "too_dark"


def test_photo_quality_accepts_clear_photo() -> None:
    image = Image.new("RGB", (420, 420), color=240)
    for x in range(120, 300):
        for y in range(120, 300):
            image.putpixel((x, y), (60, 140, 90))

    issue = detect_photo_quality_issue(_image_bytes(image))

    assert issue is None


def test_catalog_normalize_handles_case_and_yo() -> None:
    assert normalize_food_text("  ЁГУРТ, KFC!  ") == "егурт kfc"


def test_catalog_scales_estimate_preserving_metadata() -> None:
    estimate = FoodEstimate(
        name="наггетсы KFC",
        weight_g=100,
        kcal=270,
        protein=16,
        fat=17,
        carbs=15,
        source_label="Фастфуд",
        catalog_id=42,
        trust_score=0.9,
    )

    scaled = scale_estimate(estimate, 1.5)

    assert scaled.weight_g == 150
    assert scaled.kcal == 405
    assert scaled.protein == 24
    assert scaled.catalog_id == 42
    assert scaled.source_label == "Фастфуд"


def test_catalog_learning_rejects_low_confidence_payload() -> None:
    payload = FoodEntryCreate(
        name="пирожок",
        weight_g=100,
        kcal=240,
        protein=6,
        fat=8,
        carbs=35,
        confidence=0.4,
        source="manual",
    )

    assert not _can_learn(payload)


def test_catalog_specific_name_beats_generic_alias() -> None:
    from kcal_tracker.models import FoodCatalogItem

    generic = FoodCatalogItem(
        food_name="ролл с курицей",
        normalized_name="ролл с курицей",
        kcal=210,
        protein=10,
        fat=9,
        carbs=22,
        source="curated",
        trust_score=0.95,
        usage_count=0,
    )
    branded = FoodCatalogItem(
        food_name="ростикс твистер оригинальный",
        normalized_name="ростикс твистер оригинальный",
        kcal=570,
        protein=26,
        fat=31,
        carbs=47,
        source="seed",
        trust_score=0.82,
        usage_count=0,
    )

    generic_score = _score_text_match("твистер", "твистер", generic)
    branded_score = _score_text_match("твистер", "твистер", branded)

    assert branded_score > generic_score


def test_catalog_seed_has_enough_common_foods_and_aliases() -> None:
    rows = read_catalog_seed("data/food_catalog_seed.csv")

    assert len(rows) >= 90
    by_name = {row.name: row for row in rows}
    assert "гречка вареная" in by_name
    assert "куриная грудка" in by_name
    assert "борщ" in by_name
    assert "сырники" in by_name
    assert "гречневая каша" in by_name["гречка вареная"].aliases
    assert by_name["яйцо куриное"].weight_g == 55


def test_catalog_seed_normalized_names_are_unique() -> None:
    rows = read_catalog_seed("data/food_catalog_seed.csv")
    normalized = [normalize_food_text(row.name) for row in rows]

    assert len(normalized) == len(set(normalized))


def _jpeg_bytes(size: tuple[int, int], *, color: int) -> bytes:
    return _image_bytes(Image.new("RGB", size, color=color))


def _image_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="JPEG", quality=95)
    return output.getvalue()

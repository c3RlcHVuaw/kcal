from __future__ import annotations

from kcal_tracker.services.open_food_facts import _is_relevant_product, _search_queries


def test_search_queries_simplify_ocr_product_text() -> None:
    queries = _search_queries(
        "(RUS) КОКТЕЙЛЬ МОЛОЧНЫЙ ПАСТЕРИЗОВАННЫЙ, ОБОГАЩЕННЫЙ "
        "МОЛОЧНЫМ БЕЛКОМ СО ВКУСОМ ЛЕСНОГО ОРЕХА И КОФЕ «ОРЕХОВЫЙ ЛАТТЕ»."
    )

    assert queries[0] == "ореховый латте"
    assert "коктейль молочный кофе ореховый латте" in queries
    assert "кофе ореховый латте" in queries


def test_relevant_product_requires_matching_food_words() -> None:
    product = {"product_name_ru": "Коктейль молочный Ореховый латте", "nutriments": {}}

    assert _is_relevant_product(product, "ореховый латте") is True
    assert _is_relevant_product({"product_name_ru": "Томатный кетчуп"}, "ореховый латте") is False

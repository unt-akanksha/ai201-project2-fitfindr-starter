# tests/test_tools.py

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

# ── search_listings tests ─────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    # This should return [] not crash
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)

def test_search_size_filter():
    # "M" should match "S/M" and "M" listings
    results = search_listings("top", size="M", max_price=100)
    assert all("m" in item["size"].lower() for item in results)

def test_search_returns_max_five():
    # Broad search — should never return more than 5
    results = search_listings("vintage", size=None, max_price=1000)
    assert len(results) <= 5

# ── suggest_outfit tests ──────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    item = search_listings("vintage tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0

def test_suggest_outfit_empty_wardrobe():
    # Should NOT crash — should return generic advice
    item = search_listings("vintage tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0  # still returns something useful

# ── create_fit_card tests ─────────────────────────────────────────────────────

def test_fit_card_returns_string():
    item = search_listings("vintage tee", size=None, max_price=50)[0]
    outfit = suggest_outfit(item, get_example_wardrobe())
    card = create_fit_card(outfit, item)
    assert isinstance(card, str)
    assert len(card) > 0

def test_fit_card_empty_outfit_guard():
    # Empty outfit should return fallback, not crash
    fake_item = {"title": "Test item", "price": 20, "platform": "depop"}
    result = create_fit_card("", fake_item)
    assert result == "found something worth adding to the rotation 🛍️"
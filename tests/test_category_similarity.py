from __future__ import annotations

from finance_cli.cli import _find_similar_categorization, _rank_categories


def test_rank_categories_uses_similarity() -> None:
    candidates = [
        ("amazon marketplace", "shopping"),
        ("spotify", "subscriptions"),
    ]
    counts = {"shopping": 3, "subscriptions": 1}
    ranked = _rank_categories("am azon marketp", candidates, counts, top=1)
    assert ranked[0][0] == "shopping"


def test_find_similar_categorization_threshold() -> None:
    candidates = [
        ("amazon marketplace", "shopping", None, "amazonmarketplace"),
        ("spotify", "subscriptions", None, "spotify"),
    ]
    match = _find_similar_categorization("am azon marketp", candidates, threshold=0.8)
    assert match == ("shopping", None)

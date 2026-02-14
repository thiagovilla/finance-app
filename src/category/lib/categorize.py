from dataclasses import replace
from typing import List

from category.models import Suggestion, Category
from category.repo import get_all_statements, get_all_unnormalized_statements
from core.common import canonicalize_description, Statement
from core.db import connect_db
from category.ai import ask_single


def find_exact_match(conn, canonical_description: str) -> Category | None:
    """
    Look for an exact match in the categorizations table using the canonical description.
    """
    row = conn.execute(
        "SELECT category FROM categorizations WHERE canonical_description = ?",
        (canonical_description,),
    ).fetchone()
    return row[0] if row else None


def fuzzy_search(normalized_description: str, limit=5) -> List[Suggestion]:
    """
    Use FTS5 to find similar descriptions and return suggestions with confidence scores.
    """
    rows = conn.execute(
        """
        SELECT category, rank
        FROM categorizations_fts
        WHERE categorizations_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (normalized_description, limit),
    ).fetchall()

    if not rows:
        return []

    # Normalize BM25 scores to confidence (0-1 range)
    # BM25 rank is negative; higher (closer to 0) is better
    max_rank = rows[0][1] if rows else -100
    min_rank = rows[-1][1] if len(rows) > 1 else max_rank - 1
    rank_range = max_rank - min_rank if max_rank != min_rank else 1

    suggestions = []
    for category_name, rank in rows:
        confidence = (rank - min_rank) / rank_range if rank_range > 0 else 1.0
        suggestions.append(Suggestion(
            category=Category(name=category_name),
            confidence=confidence
        ))

    return suggestions


def auto_categorize(statements: list[Statement], threshold=0.85, stats=None):
    stats = {"exact_matches": 0, "fuzzy_matches": 0, "ask_ai": 0, "updated": 0, "skipped": 0, "errors": 0}
    ask_ai_list = []
    categorized_stmts = []
    my_dict = {
        "stmt_id": 0,
        "old_category": None,
        "new_category": None,
        "strategy": "exact | fuzzy | ai",
        "confidence": 0.0
    }
    for stmt in statements:
        category = None
        if exact_match := find_exact_match(stmt.normalized_description):
            category = exact_match.name

        if category is None and (suggestions := fuzzy_search(stmt.normalized_description, 1)):
            if suggestions[0].confidence >= threshold:
                category = suggestions[0].category

        if category:
            categorized_stmts.append(replace(stmt, category=category))
        else:
            ask_ai_list.append(stmt)

    if ask_ai_list:
        suggestions = batch_ask_ai(ask_ai_list)  # returns tuple of (stmt_id, category, confidence)
        for suggestion in suggestions:
            if suggestion[2] < threshold:
                continue
            categorized_stmts.append(replace(statements[suggestion[0]], category=suggestion[1]))

    batch_update_categories([(s[0], s[1]) for s in categorized_stmts])

    return stats

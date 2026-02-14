from dataclasses import replace
from typing import List

from category.lib.ai import batch_ask_ai
from category.models import Suggestion, Category
from core.common import Statement


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
    with db_connect() as conn:
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


def auto_categorize(statements: list[Statement], threshold=0.85) -> tuple[list[Statement], dict]:
    stats = {"exact_matches": 0, "fuzzy_matches": 0, "ask_ai": 0, "updated": 0, "failed": 0}
    ask_ai_list: list[Statement] = []
    categorized_stmts: list[Statement] = []

    for stmt in statements:
        category = None
        if exact_match := find_exact_match(stmt.normalized_description):
            category = exact_match.name
            stats["exact_matches"] += 1

        if category is None and (suggestions := fuzzy_search(stmt.normalized_description, 1)):
            if suggestions[0].confidence >= threshold:
                category = suggestions[0].category
                stats["fuzzy_matches"] += 1

        if category:
            categorized_stmts.append(replace(stmt, category=category))
        else:
            ask_ai_list.append(stmt)

    if ask_ai_list:
        ai_suggestions = batch_ask_ai(ask_ai_list)
        for i, suggestion in enumerate(ai_suggestions):
            if suggestion.confidence >= threshold:
                categorized_stmts.append(replace(ask_ai_list[i], category=suggestion.category))
                stats["ask_ai"] += 1
            else:
                stats["failed"] += 1

    stats["updated"] = len(categorized_stmts)
    return categorized_stmts, stats

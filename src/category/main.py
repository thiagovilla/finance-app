from dataclasses import dataclass
from typing import List

from core.common import canonicalize_description
from core.db import connect_db
from ai import ask_single


@dataclass(frozen=True)
class Category:
    name: str
    description: str = ""


@dataclass(frozen=True)
class Suggestion:
    category: Category
    confidence: float


def categorize(description: str, threshold=0.85, ai_hint=""):
    """
    Control flow for categorizing a description.
    """
    canonical_description = canonicalize_description(description)

    with connect_db() as conn:
        # 1. Exact match (O(1) lookup)
        if category := find_exact_match(conn, canonical_description):
            return category

        # 2. Fuzzy search (SQLite FTS5)
        search_results = fuzzy_search(conn, canonical_description, 1)
        if search_results and search_results[0].confidence >= threshold:
            return search_results[0].category

        # 3. AI hint / Fallback
        ai_matches = ask_single(description, hint=ai_hint, top=1)
        if ai_matches and ai_matches[0].confidence >= threshold:
            return ai_matches[0].category

    return None


def find_exact_match(conn, canonical_description: str) -> Category | None:
    """
    Look for an exact match in the categorizations table using the canonical description.
    """
    row = conn.execute(
        "SELECT category FROM categorizations WHERE canonical_description = ?",
        (canonical_description,),
    ).fetchone()
    return row[0] if row else None


def fuzzy_search(conn, canonical_description: str, limit=5) -> List[Suggestion]:
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
        (canonical_description, limit),
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

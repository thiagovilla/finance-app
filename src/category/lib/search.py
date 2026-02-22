from category.models import Suggestion, Category
from core.models import Statement


def find_exact_match(statement: Statement) -> Category | None:
    """
    Look for an exact match in the categorizations table using the canonical description.
    """
    row = conn.execute(
        "SELECT category FROM categorizations WHERE canonical_description = ?",
        (statement.normalized_description,),
    ).fetchone()
    return row[0] if row else None


# def build_match_cache(statements: list[Statement]) -> dict[str, str]:
#     stmt_map = {stmt: stmt.normalized_description for stmt in statements}
#     unique_normalized = list(set(stmt_map.values()))
#     for match in _find_exact_match_many(unique_normalized):
#         stmt_map[stmt_map[match]] = match
#
#
# def _find_exact_match_many(foo: list[str]) -> list[str]:
#     return foo


def search_suggestions(statement: Statement, top=5) -> list[Suggestion]:
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
            (statement.normalized_description, top),
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

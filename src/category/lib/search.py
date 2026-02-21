def find_exact_match(conn, canonical_description: str) -> Category | None:
    """
    Look for an exact match in the categorizations table using the canonical description.
    """
    row = conn.execute(
        "SELECT category FROM categorizations WHERE canonical_description = ?",
        (canonical_description,),
    ).fetchone()
    return row[0] if row else None


def fuzzy_search(normalized_description: str, limit=5) -> list[Suggestion]:
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


def search_best(normalized_description: str, top = 5, threshold = 0.85) -> Suggestion | None:
    suggestions = fuzzy_search(normalized_description, top=top, threshold=threshold)
    for suggestion in suggestions:
        if suggestion.confidence >= threshold:
            return suggestion
    return None
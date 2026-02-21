import sqlite3
from datetime import date
from core.db import connect_db
from core.models import Statement


def _row_to_statement(row: sqlite3.Row) -> Statement:
    """Helper to convert a database row to a Statement dataclass."""
    return Statement(
        id=row["raw_import_id"],
        transaction_date=date.fromisoformat(row["txn_date"]),
        description=row["description"],
        amount=row["amount_cents"] / 100.0,
        payment_date=date.fromisoformat(row["post_date"]) if row["post_date"] else None,
        category=row["category"] or "",
        location=row["location"] or "",
        tags=row["tags"] or "",
        account=row["source"]
    )


def get_all_statements() -> list[Statement]:
    """Retrieve all statements and convert cents to float for the dataclass."""
    with connect_db() as conn:
        conn._raw.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM statements")
        rows = cursor.fetchall()

    return [_row_to_statement(row) for row in rows]


def get_all_unnormalized_statements() -> list[Statement]:
    """Retrieve statements where normalized_description is missing/empty."""
    with connect_db() as conn:
        conn._raw.row_factory = sqlite3.Row
        # Adjusting the query to match the schema in db.py
        cursor = conn.execute(
            "SELECT * FROM statements WHERE normalized_description = '' OR normalized_description IS NULL"
        )
        rows = cursor.fetchall()

    return [_row_to_statement(row) for row in rows]


def batch_update_normalized_descriptions(updates: list[tuple[str, str]]) -> int:
    """
    Update multiple statements in a single transaction.
    Args:
        updates: A list of tuples containing (normalized_description, statement_id)
    Returns:
        The number of rows affected.
    """
    try:
        with connect_db() as conn:
            cursor = conn.executemany(
                "UPDATE statements SET normalized_description = ? WHERE id = ?",
                updates,
            )
            return cursor.rowcount
    except Exception:
        return 0


def get_uncategorized_counts() -> list[tuple[str, int]]:
    """
    Retrieve uncategorized normalized descriptions with their frequency count.
    Returns:
        List of tuples containing (normalized_description, count)
    """
    with connect_db() as conn:
        cursor = conn.execute(
            """
            SELECT normalized_description, COUNT(*) as count
            FROM statements
            WHERE (category IS NULL OR category = '')
            GROUP BY normalized_description
            ORDER BY count DESC
            """
        )
        return cursor.fetchall()

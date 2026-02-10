from __future__ import annotations
from datetime import datetime, timezone
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from common import canonicalize_description

EN_US_MONTH_ABBREVIATIONS = [
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
]


@dataclass(frozen=True)
class DatabaseConfig:
    kind: str
    dsn: str
    sqlite_path: Path | None


def resolve_database(value: "str | Path | DatabaseConfig") -> DatabaseConfig:
    if isinstance(value, DatabaseConfig):
        return value
    if isinstance(value, Path):
        return DatabaseConfig(kind="sqlite", dsn=str(value), sqlite_path=value)

    parsed = urlparse(value)
    if parsed.scheme == "sqlite":
        path = Path(parsed.path or parsed.netloc)
        return DatabaseConfig(kind="sqlite", dsn=str(path), sqlite_path=path)
    if parsed.scheme:
        raise ValueError(
            "Only SQLite is supported. Use a file path or sqlite:/// URL."
        )

    return DatabaseConfig(kind="sqlite", dsn=value, sqlite_path=Path(value))


class DBConnection:
    def __init__(self, *, kind: str, raw) -> None:
        self.kind = kind
        self._raw = raw

    def execute(self, sql: str, params: Iterable | None = None):
        sql = _normalize_sql(sql, self.kind)
        cursor = self._raw.cursor()
        if params is None:
            cursor.execute(sql)
        else:
            cursor.execute(sql, params)
        return cursor

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()


@dataclass(frozen=True)
class ImportResult:
    inserted: int
    skipped: int


@dataclass(frozen=True)
class Categorization:
    canonical_description: str
    category: str
    tags: str | None
    confidence: float | None
    source: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class StatementPreview:
    id: int
    source: str
    txn_date: str
    description: str
    canonical_description: str
    amount_cents: int


def init_db(db_value: str | Path | DatabaseConfig) -> None:
    db = resolve_database(db_value)
    if db.kind == "sqlite":
        assert db.sqlite_path is not None
        db.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with connect_db(db) as conn:
        for statement in _schema_statements(db.kind):
            conn.execute(statement)


def upsert_statement(
        conn: DBConnection,
        *,
        source: str,
        txn_date: str,
        post_date: str | None,
        description: str,
        amount_cents: int,
        currency: str,
        raw_import_id: str,
        category: str | None,
        tags: str | None,
        location: str | None = None,
) -> bool:
    canonical = canonicalize_description(description)
    created_at = _now_iso()
    cursor = conn.execute(
        """
        INSERT INTO statements (
            source,
            txn_date,
            post_date,
            description,
            canonical_description,
            amount_cents,
            currency,
            raw_import_id,
            category,
            tags,
            location,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(raw_import_id) DO UPDATE SET
            source=excluded.source,
            txn_date=excluded.txn_date,
            post_date=excluded.post_date,
            description=excluded.description,
            canonical_description=excluded.canonical_description,
            amount_cents=excluded.amount_cents,
            currency=excluded.currency,
            category=excluded.category,
            tags=excluded.tags,
            location=excluded.location
        """,
        (
            source,
            txn_date,
            post_date,
            description,
            canonical,
            amount_cents,
            currency,
            raw_import_id,
            category,
            tags,
            location,
            created_at,
        ),
    )
    return cursor.rowcount == 1


def fetch_uncategorized_canonicals(
        conn: DBConnection,
        source: str | None = None,
) -> list[str]:
    query = (
        "SELECT DISTINCT canonical_description FROM statements "
        "WHERE (category IS NULL OR category = '')"
    )
    params: list[str] = []
    if source:
        query += " AND source = ?"
        params.append(source)
    rows = conn.execute(query, params).fetchall()
    return [row[0] for row in rows]


def get_categorization(
        conn: DBConnection,
        canonical_description: str,
) -> Categorization | None:
    row = conn.execute(
        """
        SELECT canonical_description, category, tags, confidence, source,
               created_at, updated_at
        FROM categorizations
        WHERE canonical_description = ?
        """,
        (canonical_description,),
    ).fetchone()
    if row is None:
        return None
    return Categorization(
        canonical_description=row[0],
        category=row[1],
        tags=row[2],
        confidence=row[3],
        source=row[4],
        created_at=row[5],
        updated_at=row[6],
    )


def get_setting(conn: DBConnection, key: str) -> str | None:
    row = conn.execute(
        """
        SELECT value
        FROM settings
        WHERE key = ?
        """,
        (key,),
    ).fetchone()
    if row is None:
        return None
    return row[0]


def upsert_setting(conn: DBConnection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value=excluded.value,
            updated_at=excluded.updated_at
        """,
        (key, value, _now_iso()),
    )


def upsert_categorization(
        conn: DBConnection,
        canonical_description: str,
        category: str,
        tags: str | None,
        confidence: float | None,
        source: str,
) -> None:
    now = _now_iso()
    upsert_categorization_full(
        conn,
        canonical_description=canonical_description,
        category=category,
        tags=tags,
        confidence=confidence,
        source=source,
        created_at=now,
        updated_at=now,
    )


def upsert_categorization_full(
        conn: DBConnection,
        *,
        canonical_description: str,
        category: str,
        tags: str | None,
        confidence: float | None,
        source: str,
        created_at: str,
        updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO categorizations (
            canonical_description,
            category,
            tags,
            confidence,
            source,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(canonical_description) DO UPDATE SET
            category=excluded.category,
            tags=excluded.tags,
            confidence=excluded.confidence,
            source=excluded.source,
            updated_at=excluded.updated_at
        """,
        (
            canonical_description,
            category,
            tags,
            confidence,
            source,
            created_at,
            updated_at,
        ),
    )


def apply_categorization_to_statements(
        conn: DBConnection,
        canonical_description: str,
        category: str,
        tags: str | None,
) -> int:
    cursor = conn.execute(
        """
        UPDATE statements
        SET category = ?, tags = ?
        WHERE canonical_description = ?
          AND (category IS NULL OR category = '')
        """,
        (category, tags, canonical_description),
    )
    return cursor.rowcount


def get_sample_statement_by_canonical(
        conn: DBConnection,
        canonical_description: str,
        source: str | None = None,
) -> StatementPreview | None:
    query = (
        "SELECT id, source, txn_date, description, canonical_description, amount_cents "
        "FROM statements WHERE canonical_description = ?"
    )
    params: list[str] = [canonical_description]
    if source:
        query += " AND source = ?"
        params.append(source)
    query += " ORDER BY txn_date, id LIMIT 1"
    row = conn.execute(query, params).fetchone()
    if row is None:
        return None
    return StatementPreview(
        id=int(row[0]),
        source=row[1],
        txn_date=row[2],
        description=row[3],
        canonical_description=row[4],
        amount_cents=int(row[5]),
    )


def get_statement_by_id(
        conn: DBConnection,
        statement_id: int,
) -> StatementPreview | None:
    row = conn.execute(
        """
        SELECT id, source, txn_date, description, canonical_description, amount_cents
        FROM statements
        WHERE id = ?
        """,
        (statement_id,),
    ).fetchone()
    if row is None:
        return None
    return StatementPreview(
        id=int(row[0]),
        source=row[1],
        txn_date=row[2],
        description=row[3],
        canonical_description=row[4],
        amount_cents=int(row[5]),
    )


def find_statements_by_description(
        conn: DBConnection,
        description_glob: str,
        source: str | None = None,
        limit: int = 50,
) -> list[StatementPreview]:
    like_pattern = _glob_to_like(description_glob)
    query = (
        "SELECT id, source, txn_date, description, canonical_description, amount_cents "
        "FROM statements WHERE description LIKE ? ESCAPE '\\'"
    )
    params: list[str | int] = [like_pattern]
    if source:
        query += " AND source = ?"
        params.append(source)
    query += " ORDER BY txn_date, id"
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [
        StatementPreview(
            id=int(row[0]),
            source=row[1],
            txn_date=row[2],
            description=row[3],
            canonical_description=row[4],
            amount_cents=int(row[5]),
        )
        for row in rows
    ]


def list_category_counts(conn: DBConnection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT category, COUNT(*)
        FROM statements
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category
        """
    ).fetchall()
    return {row[0]: int(row[1]) for row in rows}


def list_categorization_candidates(
        conn: DBConnection,
) -> list[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT canonical_description, category
        FROM categorizations
        """
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


def list_categorizations(
        conn: DBConnection,
) -> list[tuple[str, str, str | None, float | None, str, str, str]]:
    rows = conn.execute(
        """
        SELECT canonical_description, category, tags, confidence, source, created_at, updated_at
        FROM categorizations
        ORDER BY canonical_description
        """
    ).fetchall()
    return [
        (row[0], row[1], row[2], row[3], row[4], row[5], row[6]) for row in rows
    ]


def list_uncategorized_canonicals_with_counts(
        conn: DBConnection,
        source: str | None = None,
) -> list[tuple[str, int]]:
    query = (
        "SELECT canonical_description, COUNT(*) "
        "FROM statements "
        "WHERE (category IS NULL OR category = '')"
    )
    params: list[str] = []
    if source:
        query += " AND source = ?"
        params.append(source)
    query += " GROUP BY canonical_description ORDER BY COUNT(*) DESC, canonical_description"
    rows = conn.execute(query, params).fetchall()
    return [(row[0], int(row[1])) for row in rows]


def list_statements_with_categories(
        conn: DBConnection,
        source: str | None = None,
) -> list[tuple[str, str]]:
    query = (
        "SELECT raw_import_id, category "
        "FROM statements "
        "WHERE category IS NOT NULL AND category != ''"
    )
    params: list[str] = []
    if source:
        query += " AND source = ?"
        params.append(source)
    rows = conn.execute(query, params).fetchall()
    return [(row[0], row[1]) for row in rows]


def get_notion_sync_state(
        conn: DBConnection,
        external_id: str,
) -> tuple[str | None, bool] | None:
    row = conn.execute(
        """
        SELECT last_category, last_reconciled
        FROM notion_sync_state
        WHERE external_id = ?
        """,
        (external_id,),
    ).fetchone()
    if row is None:
        return None
    return row[0], bool(row[1])


def recanonicalize_statements(
        conn: DBConnection,
        source: str | None = None,
) -> int:
    query = "SELECT id, description, canonical_description FROM statements"
    params: list[str] = []
    if source:
        query += " WHERE source = ?"
        params.append(source)
    rows = conn.execute(query, params).fetchall()
    updated = 0
    for row in rows:
        statement_id = int(row[0])
        description = row[1]
        current = row[2]
        recalculated = canonicalize_description(description)
        if recalculated != current:
            conn.execute(
                "UPDATE statements SET canonical_description = ? WHERE id = ?",
                (recalculated, statement_id),
            )
            updated += 1
    return updated


def recanonicalize_categorizations(conn: DBConnection) -> int:
    rows = conn.execute(
        """
        SELECT canonical_description, category, tags, confidence, source, created_at, updated_at
        FROM categorizations
        """
    ).fetchall()
    grouped: dict[str, tuple[str, str | None, float | None, str, str, str]] = {}
    for row in rows:
        canonical = row[0]
        recalculated = canonicalize_description(canonical)
        category = row[1]
        tags = row[2]
        confidence = row[3]
        source = row[4]
        created_at = row[5]
        updated_at = row[6]
        existing = grouped.get(recalculated)
        if existing is None or updated_at > existing[5]:
            grouped[recalculated] = (
                category,
                tags,
                confidence,
                source,
                created_at,
                updated_at,
            )

    conn.execute("DELETE FROM categorizations")
    for canonical, record in grouped.items():
        category, tags, confidence, source, created_at, updated_at = record
        conn.execute(
            """
            INSERT INTO categorizations (
                canonical_description,
                category,
                tags,
                confidence,
                source,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                canonical,
                category,
                tags,
                confidence,
                source,
                created_at,
                updated_at,
            ),
        )
    return len(grouped)


def count_statements(conn: DBConnection, source: str | None = None) -> int:
    query = "SELECT COUNT(*) FROM statements"
    params: list[str] = []
    if source:
        query += " WHERE source = ?"
        params.append(source)
    row = conn.execute(query, params).fetchone()
    return int(row[0]) if row else 0


def count_uncategorized(conn: DBConnection, source: str | None = None) -> int:
    query = (
        "SELECT COUNT(*) FROM statements WHERE (category IS NULL OR category = '')"
    )
    params: list[str] = []
    if source:
        query += " AND source = ?"
        params.append(source)
    row = conn.execute(query, params).fetchone()
    return int(row[0]) if row else 0


@dataclass(frozen=True)
class NormalizedRow:
    transaction_date: str
    payment_date: str | None
    description: str
    amount: str
    index: str | None
    raw_id: str | None
    category: str | None
    tags: str | None
    location: str | None


def _normalize_row(row: dict[str, str | None]) -> NormalizedRow:
    def pick(*keys: str) -> str | None:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip() != "":
                return str(value).strip()
        return None

    transaction_date = pick("transaction_date", "date", "txn_date")
    description = pick("description", "desc", "details")
    amount = pick("amount", "value")

    if transaction_date is None or description is None or amount is None:
        raise ValueError("Missing required columns in CSV: date, description, amount")

    return NormalizedRow(
        transaction_date=transaction_date,
        payment_date=pick("payment_date", "post_date"),
        description=description,
        amount=amount,
        index=pick("index", "idx"),
        raw_id=pick("id"),
        category=pick("category"),
        tags=pick("tags"),
        location=pick("location"),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connect(db: DatabaseConfig):
    conn = sqlite3.connect(db.sqlite_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connect_db(db_value: str | Path | DatabaseConfig):
    db = resolve_database(db_value)
    conn = _connect(db)
    wrapper = DBConnection(kind=db.kind, raw=conn)
    try:
        yield wrapper
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _glob_to_like(pattern: str) -> str:
    escaped = pattern.replace("\\", "\\\\")
    escaped = escaped.replace("%", "\\%").replace("_", "\\_")
    escaped = escaped.replace("*", "%").replace("?", "_")
    return escaped


def _schema_statements(kind: str) -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS statements (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            txn_date TEXT NOT NULL,
            post_date TEXT,
            description TEXT NOT NULL,
            canonical_description TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'BRL',
            raw_import_id TEXT NOT NULL UNIQUE,
            category TEXT,
            tags TEXT,
            location TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_statements_canon
            ON statements(canonical_description)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_statements_date
            ON statements(txn_date)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_statements_source
            ON statements(source)
        """,
        """
        CREATE TABLE IF NOT EXISTS categorizations (
            id INTEGER PRIMARY KEY,
            canonical_description TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            tags TEXT,
            confidence REAL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS notion_sync_state (
            external_id TEXT PRIMARY KEY,
            last_category TEXT,
            last_reconciled INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """,
    ]


def _normalize_sql(sql: str, kind: str) -> str:
    return sql

from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


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


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(
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
            );

            CREATE INDEX IF NOT EXISTS idx_statements_canon
                ON statements(canonical_description);
            CREATE INDEX IF NOT EXISTS idx_statements_date
                ON statements(txn_date);
            CREATE INDEX IF NOT EXISTS idx_statements_source
                ON statements(source);

            CREATE TABLE IF NOT EXISTS categorizations (
                id INTEGER PRIMARY KEY,
                canonical_description TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                tags TEXT,
                confidence REAL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


def import_csv(
    db_path: Path,
    csv_path: Path,
    source: str,
    currency: str = "BRL",
) -> ImportResult:
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    init_db(db_path)

    inserted = 0
    skipped = 0

    with csv_path.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)

    if not rows:
        return ImportResult(inserted=0, skipped=0)

    with _connect(db_path) as conn:
        for row in rows:
            normalized = _normalize_row(row)
            txn_date = _parse_date(normalized.transaction_date)
            if txn_date is None:
                skipped += 1
                continue
            post_date = (
                _parse_date(normalized.payment_date) if normalized.payment_date else None
            )
            amount_cents = _parse_amount_cents(normalized.amount)
            canonical = canonicalize_description(normalized.description)
            raw_import_id = normalized.raw_id or _hash_import_id(
                source=source,
                txn_date=txn_date,
                post_date=post_date,
                description=normalized.description,
                amount_cents=amount_cents,
            )
            created_at = _now_iso()

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO statements (
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
                """,
                (
                    source,
                    txn_date,
                    post_date,
                    normalized.description,
                    canonical,
                    amount_cents,
                    currency,
                    raw_import_id,
                    normalized.category,
                    normalized.tags,
                    normalized.location,
                    created_at,
                ),
            )
            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

    return ImportResult(inserted=inserted, skipped=skipped)


def fetch_uncategorized_canonicals(
    conn: sqlite3.Connection,
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
    conn: sqlite3.Connection,
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


def upsert_categorization(
    conn: sqlite3.Connection,
    canonical_description: str,
    category: str,
    tags: str | None,
    confidence: float | None,
    source: str,
) -> None:
    now = _now_iso()
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
            now,
            now,
        ),
    )


def apply_categorization_to_statements(
    conn: sqlite3.Connection,
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


def get_sample_description(
    conn: sqlite3.Connection,
    canonical_description: str,
) -> str | None:
    row = conn.execute(
        """
        SELECT description
        FROM statements
        WHERE canonical_description = ?
        LIMIT 1
        """,
        (canonical_description,),
    ).fetchone()
    if row is None:
        return None
    return row[0]


def get_next_uncategorized_statement(
    conn: sqlite3.Connection,
    source: str | None = None,
) -> StatementPreview | None:
    query = (
        "SELECT id, source, txn_date, description, canonical_description, amount_cents "
        "FROM statements "
        "WHERE (category IS NULL OR category = '')"
    )
    params: list[str] = []
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


def list_category_counts(conn: sqlite3.Connection) -> dict[str, int]:
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
    conn: sqlite3.Connection,
) -> list[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT canonical_description, category
        FROM categorizations
        """
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


@dataclass(frozen=True)
class NormalizedRow:
    transaction_date: str
    payment_date: str | None
    description: str
    amount: str
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
        raw_id=pick("id"),
        category=pick("category"),
        tags=pick("tags"),
        location=pick("location"),
    )


def canonicalize_description(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = "".join(
        char for char in cleaned if not unicodedata.combining(char)
    )
    cleaned = re.sub(r"\b\d{1,2}/\d{1,2}\b", " ", cleaned)
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _parse_date(value: str) -> str | None:
    value = value.strip()
    formats = [
        "%d/%m/%Y",
        "%d/%m/%y",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_amount_cents(value: str) -> int:
    cleaned = value.strip().replace(" ", "")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    amount = float(cleaned)
    return int(round(amount * 100))


def _hash_import_id(
    *,
    source: str,
    txn_date: str,
    post_date: str | None,
    description: str,
    amount_cents: int,
) -> str:
    parts = [source, txn_date, post_date or "", description, str(amount_cents)]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"sha1:{digest}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def connect_db(db_path: Path) -> sqlite3.Connection:
    return _connect(db_path)

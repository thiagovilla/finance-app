# ADR 0004: Standardized Data Pipeline (Parse & Import)

## Status

Accepted

## Context

We need a robust way to ingest data from Nubank and Itaú for the 2025 reconciliation. Previous ADRs (0001-0003) were
fragmented regarding where IDs are generated and how data is formatted.

## Decision

1. **Parser Responsibility**: All parsers (`itau.py`, `nu.py`) must output a **Standard Common Format** CSV. The parser
   is responsible for generating or extracting a deterministic `raw_import_id`.
    - For Itaú: The parser generates the ID (e.g., `YYYY-MMM-index`).
    - For Nubank: The parser uses the provided transaction ID.
2. **Standard Schema**: The CSV must use en-US formatting (ISO dates, `.` decimals) and include: id, transaction date,
   payment date (if credit card), description, amount, and account.
3. **Idempotent Importer**: The `import` module is generic. It maps the Standard CSV to the SQLite schema and uses
   `ON CONFLICT(raw_import_id) DO NOTHING` to ensure idempotency.
4. **Storage**: SQLite is the single source of truth.

## Consequences

- The database logic remains clean and source-agnostic.
- Adding new accounts only requires a new parser that adheres to the "Standard Format" contract.
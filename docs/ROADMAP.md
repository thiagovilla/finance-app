# Roadmap

## Goal

Reconcile all 2025 personal finances (Nubank Checking, Nubank Credit, Itaú Credit) using a local-first CLI and SQLite.

## Scope and guiding principles

- CLI-first now, web UI later.
- Local data (SQLite) as the source of truth.
- AI is optional and cached to control costs.
- Pareto Principle: Focus on the 20% of descriptions that cover 80% of transactions.
- Tiered Categorization: Exact Match > Keyword Search (FTS) > AI.
- Keep imports deterministic and idempotent.

## Phase 0: Baseline (current)

- CLI command: `finance parse itau <pdf>` with layout auto-detection.
- Placeholders: `finance parse nu_acc` (checking account) and `finance parse nu_cred` (credit card).
- PDF/CSV parsing via CLI for Itaú and Nubank.

## Near-term: 2025 Reconciliation Drive

- [ ] **Standard Schema**: Refactor parsers to output a unified CSV structure (ADR 0004).
- [ ] **Pareto Command**: `finance stats pareto` to identify high-volume uncategorized merchants.
- [ ] **FTS Search**: Implement keyword-based auto-categorization before resorting to AI.
- [ ] **2025 Import Audit**: Verify all 12 months of 2025 are imported without gaps or duplicates.

## Phase 1: Storage foundation

- Create SQLite schema for statements, categories, tags.
- Add import command to load CSV outputs into DB.
- Normalize descriptions and compute a canonical key.
- Ensure idempotent imports (hash or raw id).

## Phase 2: Categorization cache

- Add categorization table keyed by canonical description.
- Implement cache lookup before AI calls.
- Store confidence, source, timestamps.
- CLI command: `finance categorize` to backfill and/or update.

## Phase 3: Standardized Pipeline (Current)

- [x] SQLite schema for statements and categorizations.
- [ ] **Standard Format**: Refactor `nu.py` and `itau.py` to output the ADR 0004 schema.
- [ ] **Unified Import**: Ensure `finance import` works identically for all processed CSVs.
- [ ] **2025 Audit**: Import all 12 months of 2025 data to establish the baseline.

## Phase 4: Pareto & Search

- [ ] **Pareto View**: Command to show coverage (e.g., "Top 10 merchants = 45% of transactions").
- [ ] **FTS Integration**: Add SQLite full-text search for Tier 2 categorization.

## Phase 5: Query + tagging agent (CLI)

- CLI command to run natural language queries against DB.
- Preview matching statements before tagging.
- Apply tags and save back to DB.
- Basic saved queries or tag presets.

## Phase 6: Analysis (later)

- Monthly summaries, merchant rollups, category trends.
- Export views as CSV for further analysis.

## Phase 7: Web UI (later)

- Read-only dashboard initially.
- Tagging and categorization UI.
- Authentication and local-first storage strategy.

## Open questions

- Canonicalization rules for description normalization.
- Category taxonomy vs free-form categories.
- AI provider abstraction and local model support.
- Data privacy and encryption at rest.

# Roadmap

## Goal
Build a local-first personal finance CLI that parses statements and imports data into Notion for AI analysis, while keeping the door open for local storage, tagging, and a future web UI.

## Scope and guiding principles
- CLI-first now, web UI later.
- Local data (SQLite) as the source of truth.
- AI is optional and cached to control costs.
- Simple tagging and flexible categories.
- Keep imports deterministic and idempotent.

## Phase 0: Baseline (current)
- CLI command: `finance parse itau <pdf>` with layout auto-detection.
- Placeholders: `finance parse nu_acc` (checking account) and `finance parse nu_cred` (credit card).
- PDF/CSV parsing via CLI for Itaú and Nubank.

## Near-term improvements
- Fine-tune PDF annotation with explicit start/end markers.
- Rework debug mode for clearer tracing and easier troubleshooting.

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

## Phase 3: Query + tagging agent (CLI)
- CLI command to run natural language queries against DB.
- Preview matching statements before tagging.
- Apply tags and save back to DB.
- Basic saved queries or tag presets.

## Phase 4: Analysis (later)
- Monthly summaries, merchant rollups, category trends.
- Export views as CSV for further analysis.

## Phase 5: Web UI (later)
- Read-only dashboard initially.
- Tagging and categorization UI.
- Authentication and local-first storage strategy.

## Open questions
- Canonicalization rules for description normalization.
- Category taxonomy vs free-form categories.
- AI provider abstraction and local model support.
- Data privacy and encryption at rest.

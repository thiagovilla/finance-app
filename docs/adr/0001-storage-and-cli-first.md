# Storage and CLI-first architecture

## Status
Accepted

## Context
We need a fast, local-first workflow to ingest statements, run cached AI categorization, and tag/query results. The current CLI parses Itaú and Nubank statements into CSV, but there is no persistent storage or query layer. A web UI is desired later, but the initial workflow should be CLI-based.

## Decision
Use SQLite as the local source of truth and implement a CLI-first workflow for importing, categorizing, tagging, and querying statements. Categorization will be cached by canonicalized description to minimize AI costs. The design should keep the data model compatible with a future web UI.

## Consequences
- Pros: fast local queries, deterministic imports, AI cost control, easy backup.
- Cons: requires schema design and migration strategy, and careful canonicalization.
- Follow-ups: add import commands, schema migrations, and AI provider abstraction.

# SQLite-only storage and en-US CSV output

## Status
Accepted

## Context
We want a simple, local-first workflow and a consistent CSV format for
data interchange. Postgres adds operational overhead that isn't needed for a
single-user CLI. Locale-specific output formats complicate imports and tooling.

## Decision
Use SQLite as the only supported database backend. CSV output always uses
en-US formatting (dates `MM/DD/YY`, decimal `.`).

## Consequences
- Pros: simpler setup, fewer dependencies, consistent data exchange format.
- Cons: no remote database sharing; no locale-specific CSV output.

# ADR 0005: Tiered Pareto Categorization

## Status

Accepted

## Context

Reconciling a full year of data requires high efficiency. Pure AI is too slow/expensive, and pure manual is too tedious.

## Decision

1. **Pareto Ordering**: The system will prioritize uncategorized transactions by frequency (the "Big Rocks" first).
2. **Tiered Logic**:
    - **Tier 1 (Exact)**: Matches on `canonical_description` against the cache.
    - **Tier 2 (Search)**: Keyword-based matching (SQLite FTS5) to find similar historical merchants.
    - **Tier 3 (AI)**: LLM-based suggestion only when Tiers 1 and 2 fail.
3. **Manual Override**: The CLI always allows the user to define a new category, which is then cached for future Tier 1
   matches.

## Consequences

- Faster "time-to-reconciled" for 2025 data.
- Massive reduction in AI dependency and cost.
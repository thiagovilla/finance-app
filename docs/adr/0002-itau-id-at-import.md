# Itaú IDs generated at import

## Status
Accepted

## Context
Itaú PDFs do not contain stable transaction IDs. We want deterministic IDs across
re-imports, and payment dates are always present. We only support one Itaú card
per invoice month.

## Decision
Itaú parsing outputs an `index` column instead of an `id`. Import builds the id
as `YYYY-MMM-index`, using `payment_date` to derive the year and month.

## Consequences
- Pros: stable IDs across re-imports without guessing a PDF-specific ID format.
- Cons: Itaú CSV output is template-specific (no standard `id` column).
- Constraint: multiple Itaú cards in the same month would need an additional
  disambiguator.

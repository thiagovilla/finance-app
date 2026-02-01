# finances-app

Personal finance CLI that parses statements and produces CSV output.

## Quickstart

- Create a virtual env and install deps with uv:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

- Run the CLI:

```bash
finance --help
```

## Commands

### Parse

```bash
finance parse <pdf|csv> [options]
```

Parses statements into CSV format:
- Itaú: `index`, `transaction_date`, `payment_date`, `description`, `amount` (plus optional columns).
- Nubank: `id`, `transaction_date`, `payment_date`, `description`, `amount` (plus optional columns).

Itaú ids are generated during import from `payment_date` and `index`.

Templates:
- `itau_cc` (PDF)
- `nu_cred` (CSV)
- `nu_acc` (CSV)

Auto-detection is based on file type, CSV headers, and filename hints. Override with `-t/--template`.

Examples:

```bash
finance parse Fatura.pdf
finance parse "faturas/*.pdf" -s "transaction_date DESC"
finance parse "faturas/*.pdf" -m -o merged.csv
finance parse Itau.pdf --total 9356.73
finance parse nubank.csv -t nu_cred
```

### Import

```bash
finance import <csv> [--source itau_cc|nu_cred|nu_acc]
```

Imports a standard-format CSV into the database (SQLite).
If `--source` is omitted,
the CLI tries to infer it from a `source` column or the filename.

### Category

Bulk apply cached categorizations (no AI in bulk mode):

```bash
finance category --db finances.db
```

Manually categorize with Pareto ordering (most frequent descriptions first):

```bash
finance category manual
```

If installment labels (e.g. `02/10`) are preventing grouping, re-canonicalize:

```bash
finance category recanon
```

Export/import the category cache:

```bash
finance category cache export --file categorizations.csv
finance category cache import --file categorizations.csv
```

Force AI suggestions for every item:

```bash
finance category manual --force
```

Find a statement by id or description glob, suggest categories, and cache the result:

```bash
finance category find "IFOOD*"
finance category find 123
```

If there are no cached suggestions yet, `category find` falls back to AI and requires
`OPENAI_API_KEY`. You can store this in a `.env` file (see `.env.example`).

### Prompt

Store the categorization prompt in the database so it syncs across machines:

```bash
finance category prompt set --file prompts/categorization_prompt.txt
```

Read the stored prompt:

```bash
finance category prompt get
```

## Sync

Pull from Notion into the local cache:

```bash
finance sync pull
finance sync pull --since 2024-01-01T00:00:00Z
```

Push category/reconciled updates to Notion (only changed records by default):

```bash
finance sync push
finance sync push --force
```

### Group / Export

These commands are placeholders for now:

```bash
finance group
finance export
```

## Debug output

Debug output modes:
- `all` (default): raw text + normalized text + scanned total
- `raw`: raw text only
- `normalized`: normalized text only
- `total`: scanned total only

The normalized text strips accents, lowercases, and removes whitespace so
PDF spacing artifacts are easier to diagnose.

## Output format

CSV output uses en-US formatting for data interchange:
- Dates are `MM/DD/YY`
- Amounts use `.` as decimal separator

## Itaú layouts

- `modern` (default): Aug 2025+ statements.
- `legacy`: Jul 2025 and earlier; split uses midpoint on page 1 and shifts 1.5cm right on page 2+.

## Sorting

Sort columns supported:
- `index`
- `transaction_date`
- `payment_date`
- `description`
- `amount`

Example:

```bash
finance parse Fatura.pdf -s "amount DESC"
```

## Tests

```bash
pytest
```

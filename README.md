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

Parses statements into the standard CSV format:
`id`, `transaction_date`, `payment_date`, `description`, `amount` (plus optional columns).

Templates:
- `itau_cc` (PDF)
- `nubank_cc` (CSV)
- `nubank_chk` (CSV)

Auto-detection is based on file type, CSV headers, and filename hints. Override with `-t/--template`.

Examples:

```bash
finance parse Fatura.pdf
finance parse "faturas/*.pdf" -s "transaction_date DESC"
finance parse "faturas/*.pdf" -m -o merged.csv
finance parse Itau.pdf --total 9356.73
finance parse nubank.csv -t nubank_cc
```

### Import

```bash
finance import <csv> [--source itau_cc|nubank_cc|nubank_chk]
```

Imports a standard-format CSV into the database (SQLite by default, Postgres via URL).
If `--source` is omitted,
the CLI tries to infer it from a `source` column or the filename.

### Category

Bulk apply cached categorizations (no AI in bulk mode):

```bash
finance category --db finances.db
```

Find a statement by id or description glob, suggest categories, and cache the result:

```bash
finance category find "IFOOD*"
finance category find 123
```

Use a Postgres URL to share data across machines:

```bash
export DATABASE_URL="postgresql://user:password@host:5432/finances"
finance import statements.csv
finance category find "IFOOD*"
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

## Postgres (Docker)

Run a disposable Postgres container with a persistent volume:

```bash
scripts/run-postgres.sh
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

## Output localization

By default:
- Dates are `MM/DD/YY`
- Amounts use `.` as decimal separator

Use `--locale pt-br` for:
- Dates `DD/MM/YY`
- Amounts with `,` as decimal separator

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

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

### Itaú PDF parser

```bash
finance itau <pdf|folder|glob> [options]
```

Output columns (default, with headers):

1. `index` (match order in the PDF)
2. `transaction_date` (charge date)
3. `payment_date` (statement due date)
4. `description`
5. `amount`

Notes:
- Amounts are parsed from the PDF and sign is flipped to match cash-flow style.
- The year comes from the PDF "Emissao" date when available.
- The payment date comes from the PDF "Vencimento" date.
- Output is en-us locale by default (MM/DD/YY and dot decimals).
- When multiple PDFs are provided, a CSV is written next to each PDF by default.

Options:
- `-y, --year` Override the year (YY) used for dates.
- `-t, --total` Manual checksum total (e.g. `1234.56` or `1.234,56`).
- `-s, --sort` Sort output by `<column> [ASC|DESC]`.
- `-m, --merge` Merge multiple PDFs into a single CSV output.
- `-l, --locale` Output locale: `en-us` (default) or `pt-br`.
- `-n, --no-headers` Omit CSV headers.
- `-o, --output` Write output to a CSV file (idempotent append).
- `-d, --debug` Dump debug output and exit. Optional mode: `all`, `raw`, `total`, `normalized`.

Examples:

```bash
finance itau Fatura.pdf
finance itau "faturas/*.pdf" -s "transaction_date DESC"
finance itau "faturas/*.pdf" -m -o merged.csv
finance itau Fatura.pdf -l pt-br -n
finance itau Fatura.pdf -t 9356.73
finance itau Fatura.pdf -d total
finance itau Fatura.pdf -d raw
```

### Nu CSV normalizer

```bash
finance nu <csv> [-o output.csv]
```

Normalizes Nu CSV date format and flips amounts.

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

## Sorting

Sort columns supported:
- `index`
- `transaction_date`
- `payment_date`
- `description`
- `amount`

Example:

```bash
finance itau Fatura.pdf -s "amount DESC"
```

## Tests

```bash
pytest
```

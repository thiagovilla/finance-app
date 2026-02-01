from __future__ import annotations

from pathlib import Path
from datetime import datetime
from enum import Enum
import csv
import glob
import os

import typer

from finance_cli.itau import (
    blocks_to_statements,
    blocks_to_statements_with_layout,
    extract_blocks,
    extract_blocks_with_layout,
    extract_total_from_pdf,
    extract_raw_text,
    extract_emissao_year,
    extract_invoice_payment_date,
    extract_card_last4,
    flip_sign_last_column,
    localize_rows,
    apply_id_schema,
    check_total,
    write_csv_lines,
    write_csv_lines_idempotent,
    parse_brl_amount,
    annotate_pdf_blocks,
    CSV_HEADERS,
    CSV_HEADERS_ENHANCED,
    Layout,
    month_number_for_date,
)
from finance_cli.nu import parse_nubank_csv
from finance_cli.ai import suggest_categories
from finance_cli.db import (
    ImportResult,
    apply_categorization_to_statements,
    connect_db,
    fetch_uncategorized_canonicals,
    find_statements_by_description,
    get_categorization,
    get_statement_by_id,
    import_csv,
    init_db,
    list_categorization_candidates,
    list_category_counts,
    resolve_database,
    upsert_categorization,
)

app = typer.Typer(help="Personal finance CLI.")


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


_load_dotenv()


class Locale(str, Enum):
    en_us = "en-us"
    pt_br = "pt-br"

class DebugMode(str, Enum):
    all = "all"
    raw = "raw"
    total = "total"
    normalized = "normalized"
    layout = "layout"
    annotate = "annotate"


class Source(str, Enum):
    itau_cc = "itau_cc"
    nubank_cc = "nubank_cc"
    nubank_chk = "nubank_chk"


class Template(str, Enum):
    itau_cc = "itau_cc"
    nubank_cc = "nubank_cc"
    nubank_chk = "nubank_chk"


@app.command("parse")
def parse(
    input_path: str = typer.Argument(..., help="PDF or CSV to parse."),
    template: Template | None = typer.Option(
        None,
        "--template",
        "-t",
        help="Parsing template (defaults to auto-detect).",
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write output CSV (default depends on template)."
    ),
    year: str | None = typer.Option(
        None, "--year", "-y", help="Year in YY format (Itaú only)."
    ),
    total: str | None = typer.Option(
        None,
        "--total",
        help="Manual checksum total (Itaú only, e.g. 1234.56 or 1.234,56).",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Debug output (raw, total, normalized, layout, annotate, or all) and exit.",
    ),
    sort: str | None = typer.Option(
        None,
        "--sort",
        "-s",
        help="Sort output (format: '<column> <ASC|DESC>') (Itaú only).",
    ),
    layout: Layout | None = typer.Option(
        None,
        "--layout",
        "-l",
        help="PDF layout (Itaú only).",
    ),
    merge: bool = typer.Option(
        False, "--merge", "-m", help="Merge multiple PDFs into one CSV (Itaú only)."
    ),
    locale: Locale = typer.Option(
        Locale.en_us, "--locale", "-L", help="Output locale (Itaú only)."
    ),
    no_headers: bool = typer.Option(
        False, "--no-headers", "-n", help="Do not print CSV headers (Itaú only)."
    ),
    enhanced: bool = typer.Option(
        False,
        "--enhanced",
        "-e",
        help="Capture category/location when available (Itaú only).",
    ),
    rename: bool = typer.Option(
        False, "--rename", "-r", help="Rename the PDF after parsing (Itaú only)."
    ),
) -> None:
    resolved_template = template or _detect_template(input_path)
    if resolved_template == Template.itau_cc:
        parse_itau(
            input_paths=[input_path],
            year=year,
            total=total,
            debug=debug,
            sort=sort,
            layout=layout,
            merge=merge,
            locale=locale,
            no_headers=no_headers,
            enhanced=enhanced,
            output=output,
            rename=rename,
        )
        return

    _ensure_no_itau_options(
        year=year,
        total=total,
        debug=debug,
        sort=sort,
        layout=layout,
        merge=merge,
        no_headers=no_headers,
        enhanced=enhanced,
        rename=rename,
    )
    input_file = Path(input_path)
    if not input_file.exists() or input_file.is_dir():
        raise typer.BadParameter("CSV input must be a file.")
    out_path = parse_nubank_csv(
        input_file,
        output,
        template=resolved_template.value,
    )
    typer.echo(f"Wrote {out_path}")


@app.command("import")
def import_statements(
    csv_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    source: Source | None = typer.Option(
        None, "--source", "-s", help="Statement source (defaults to auto-detect)."
    ),
    db_url: str = typer.Option(
        "finances.db",
        "--db",
        "-d",
        envvar="DATABASE_URL",
        help="SQLite database path or Postgres URL.",
    ),
    currency: str = typer.Option("BRL", "--currency", "-c", help="Currency code."),
) -> None:
    """Import a standard-format CSV into the SQLite database."""
    resolved_source = source or _detect_source_from_csv(csv_path)
    if resolved_source is None:
        raise typer.BadParameter(
            "Could not determine source. Provide --source or include a source column."
        )
    db = resolve_database(db_url)
    result: ImportResult = import_csv(
        db,
        csv_path,
        resolved_source.value,
        currency=currency,
    )
    typer.echo(f"Imported {result.inserted} rows ({result.skipped} skipped)")


category_app = typer.Typer(help="Category helpers.")
app.add_typer(category_app, name="category")


@category_app.callback(invoke_without_command=True)
def category(
    ctx: typer.Context,
    db_url: str = typer.Option(
        "finances.db",
        "--db",
        "-d",
        envvar="DATABASE_URL",
        help="SQLite database path or Postgres URL.",
    ),
    source: Source | None = typer.Option(
        None, "--source", "-s", help="Statement source filter."
    ),
) -> None:
    if ctx.invoked_subcommand:
        return
    db = resolve_database(db_url)
    init_db(db)
    applied = 0
    skipped = 0

    with connect_db(db) as conn:
        canonicals = fetch_uncategorized_canonicals(
            conn, source.value if source else None
        )
        for canonical in canonicals:
            cached = get_categorization(conn, canonical)
            if cached is None:
                skipped += 1
                continue
            applied += apply_categorization_to_statements(
                conn,
                canonical,
                cached.category,
                cached.tags,
            )

    typer.echo(f"Applied {applied} cached categorizations ({skipped} skipped)")


@category_app.command("find")
def category_find(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Statement id or description glob."),
    top: int = typer.Option(5, "--top", "-t", help="Top category suggestions."),
    limit: int = typer.Option(
        20, "--limit", "-n", help="Max statements to review for glob matches."
    ),
    prompt_file: Path = typer.Option(
        Path("config/categorization_prompt.txt"),
        "--prompt-file",
        "-p",
        help="Path to categorization prompt file.",
    ),
) -> None:
    """Find a statement, suggest categories, and cache the selection."""
    db_url = ctx.parent.params["db_url"]
    source = ctx.parent.params.get("source")
    db = resolve_database(db_url)
    init_db(db)
    prompt_text = _read_prompt(prompt_file)

    with connect_db(db) as conn:
        if query.isdigit():
            stmt = get_statement_by_id(conn, int(query))
            if stmt is None:
                raise typer.BadParameter(f"No statement found for id {query}.")
            statements = [stmt]
        else:
            statements = find_statements_by_description(
                conn,
                query,
                source.value if source else None,
                limit=limit,
            )
            if not statements:
                typer.echo("No statements found.")
                return

        candidates = list_categorization_candidates(conn)
        counts = list_category_counts(conn)

        reviewed = 0
        for stmt in statements:
            amount = stmt.amount_cents / 100
            typer.echo("")
            typer.echo(
                f"[{stmt.id}] [{stmt.source}] {stmt.txn_date} {amount:.2f} - {stmt.description}"
            )

            top_ranked = _rank_categories(
                stmt.canonical_description, candidates, counts, top
            )
            cached = get_categorization(conn, stmt.canonical_description)
            if cached is not None and all(
                category != cached.category for category, _ in top_ranked
            ):
                top_ranked.insert(
                    0, (cached.category, (1.0, counts.get(cached.category, 0)))
                )
            if not top_ranked:
                top_ranked = _ai_ranked_suggestions(
                    stmt.description, top, prompt_text=prompt_text
                )
            _print_suggestions(top_ranked)

            choice = typer.prompt("Pick number, type category, (s)kip, (q)uit").strip()
            if choice.lower() in {"q", "quit"}:
                break
            if choice.lower() in {"s", "skip"}:
                reviewed += 1
                continue
            if choice.isdigit():
                index = int(choice)
                if index < 1 or index > len(top_ranked):
                    raise typer.BadParameter("Invalid selection.")
                category = top_ranked[index - 1][0]
            else:
                category = choice

            if not category:
                raise typer.BadParameter("Category cannot be empty.")

            upsert_categorization(
                conn, stmt.canonical_description, category, None, None, "manual"
            )
            apply_categorization_to_statements(
                conn, stmt.canonical_description, category, None
            )
            reviewed += 1

    typer.echo(f"Reviewed {reviewed} statements")


def _rank_categories(
    canonical: str,
    candidates: list[tuple[str, str]],
    counts: dict[str, int],
    top: int,
) -> list[tuple[str, tuple[float, int]]]:
    if not candidates:
        return []
    tokens = [token for token in canonical.split(" ") if token]
    suggestions: dict[str, tuple[float, int]] = {}
    for candidate_canonical, category in candidates:
        candidate_tokens = [token for token in candidate_canonical.split(" ") if token]
        if not tokens or not candidate_tokens:
            score = 0.0
        else:
            overlap = len(set(tokens) & set(candidate_tokens))
            score = overlap / max(1, len(set(tokens)))
        current = suggestions.get(category)
        count = counts.get(category, 0)
        if current is None or score > current[0]:
            suggestions[category] = (score, count)

    ranked = sorted(
        suggestions.items(),
        key=lambda item: (item[1][0], item[1][1], item[0]),
        reverse=True,
    )
    return ranked[: max(1, top)]


def _print_suggestions(
    ranked: list[tuple[str, tuple[float, int]]],
) -> None:
    if not ranked:
        typer.echo("Suggestions: none yet")
        return
    typer.echo("Suggestions:")
    for idx, (category, (score, count)) in enumerate(ranked, start=1):
        typer.echo(f"{idx}. {category} (score={score:.2f}, count={count})")


def _read_prompt(prompt_file: Path) -> str:
    if not prompt_file.exists():
        raise typer.BadParameter(f"Prompt file not found: {prompt_file}")
    return prompt_file.read_text(encoding="utf-8")


def _ai_ranked_suggestions(
    description: str,
    top: int,
    *,
    prompt_text: str,
) -> list[tuple[str, tuple[float, int]]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise typer.BadParameter("Missing OPENAI_API_KEY.")
    result = suggest_categories(
        description,
        model="gpt-4o-mini",
        api_key=api_key,
        prompt=prompt_text,
        top=top,
    )
    return [(category, (1.0, 0)) for category in result.categories]


@app.command("group")
def group() -> None:
    """Placeholder for future grouping features."""
    typer.echo("Group is not implemented yet.")
    raise typer.Exit(code=1)


@app.command("export")
def export() -> None:
    """Placeholder for future export features."""
    typer.echo("Export is not implemented yet.")
    raise typer.Exit(code=1)


def _detect_template(input_path: str) -> Template:
    if glob.has_magic(input_path):
        if input_path.lower().endswith(".csv"):
            raise typer.BadParameter("CSV globs are not supported; use --template.")
        return Template.itau_cc
    if Path(input_path).is_dir():
        return Template.itau_cc
    path = Path(input_path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return Template.itau_cc
    if suffix == ".csv":
        return _detect_nubank_template(path)
    raise typer.BadParameter("Unsupported input type; use --template.")


def _detect_nubank_template(path: Path) -> Template:
    header = _read_csv_header(path)
    normalized = {_normalize_header(name) for name in header}
    if normalized & {"saldo", "balance", "runningbalance"}:
        return Template.nubank_chk
    if normalized & {"categoria", "category"}:
        return Template.nubank_cc

    name = path.name.lower()
    if any(token in name for token in ["cartao", "card", "cc", "credit"]):
        return Template.nubank_cc
    if any(token in name for token in ["conta", "checking", "chk", "account"]):
        return Template.nubank_chk

    raise typer.BadParameter("Could not auto-detect template; use --template.")


def _detect_source_from_csv(csv_path: Path) -> Source | None:
    source_values = _read_source_column(csv_path)
    if source_values:
        if len(source_values) == 1:
            value = next(iter(source_values))
            try:
                return Source(value)
            except ValueError:
                return None
        return None

    name = csv_path.name.lower()
    if "itau" in name:
        return Source.itau_cc
    if "nubank" in name or "nu_" in name or name.startswith("nu"):
        if any(token in name for token in ["conta", "checking", "chk", "account"]):
            return Source.nubank_chk
        return Source.nubank_cc
    return None


def _read_source_column(csv_path: Path) -> set[str]:
    with csv_path.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        if reader.fieldnames is None or "source" not in reader.fieldnames:
            return set()
        values: set[str] = set()
        for idx, row in enumerate(reader):
            if idx >= 100:
                break
            value = (row.get("source") or "").strip()
            if value:
                values.add(value)
        return values


def _read_csv_header(csv_path: Path) -> list[str]:
    with csv_path.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        return next(reader, [])


def _normalize_header(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = cleaned.replace("-", "").replace("_", "").replace(" ", "")
    return cleaned


def _ensure_no_itau_options(
    *,
    year: str | None,
    total: str | None,
    debug: bool,
    sort: str | None,
    layout: Layout | None,
    merge: bool,
    no_headers: bool,
    enhanced: bool,
    rename: bool,
) -> None:
    invalid = []
    if year:
        invalid.append("--year")
    if total:
        invalid.append("--total")
    if debug:
        invalid.append("--debug")
    if sort:
        invalid.append("--sort")
    if layout:
        invalid.append("--layout")
    if merge:
        invalid.append("--merge")
    if no_headers:
        invalid.append("--no-headers")
    if enhanced:
        invalid.append("--enhanced")
    if rename:
        invalid.append("--rename")
    if invalid:
        raise typer.BadParameter(
            f"Options only valid for Itaú parsing: {', '.join(invalid)}"
        )


def resolve_itau_inputs(input_path: str) -> list[Path]:
    if any(char in input_path for char in ["*", "?", "["]):
        matches = [Path(path) for path in glob.glob(input_path)]
    else:
        path = Path(input_path)
        if path.is_dir():
            matches = sorted(path.glob("*.pdf"))
        else:
            matches = [path]

    pdfs = [path for path in matches if path.is_file() and path.suffix.lower() == ".pdf"]
    if not pdfs:
        raise typer.BadParameter(f"No PDF files found for input: {input_path}")
    return pdfs


def parse_itau(
    input_paths: list[str],
    year: str | None = None,
    total: str | None = None,
    debug: bool = False,
    sort: str | None = None,
    layout: Layout | None = None,
    merge: bool = False,
    locale: Locale = Locale.en_us,
    no_headers: bool = False,
    enhanced: bool = False,
    output: Path | None = None,
    rename: bool = False,
) -> None:
    """Parse Itaú credit card PDF(s) into CSV lines (id: YYYY-MMM-index)."""
    def resolve_layout(payment_date: str | None) -> Layout:
        if layout is not None:
            return layout
        if not payment_date:
            return Layout.legacy
        try:
            due_date = datetime.strptime(payment_date, "%d/%m/%y")
        except ValueError:
            return Layout.legacy
        return Layout.modern if due_date >= datetime(2025, 8, 1) else Layout.legacy

    debug_mode = DebugMode.all
    if debug and input_paths:
        first = input_paths[0].lower()
        if first in {mode.value for mode in DebugMode}:
            debug_mode = DebugMode(first)
            input_paths = input_paths[1:]

    if not input_paths:
        raise typer.BadParameter("Missing input path.")
    if len(input_paths) > 1:
        raise typer.BadParameter("Only one input path is supported.")

    pdf_paths = resolve_itau_inputs(input_paths[0])

    if debug:
        mode = debug_mode
        outputs: list[str] = []
        for pdf_path in pdf_paths:
            if len(pdf_paths) > 1:
                outputs.append(f"=== {pdf_path} ===")
            if mode in {DebugMode.all, DebugMode.total}:
                total_found = extract_total_from_pdf(pdf_path)
                if total_found is None:
                    outputs.append("total_scanned=None")
                else:
                    outputs.append(f"total_scanned={total_found:.2f}")
            if mode in {DebugMode.all, DebugMode.raw}:
                outputs.append(extract_raw_text(pdf_path))
            if mode in {DebugMode.all, DebugMode.normalized}:
                from finance_cli.itau import normalize_pdf_text
                raw_text = extract_raw_text(pdf_path)
                outputs.append(normalize_pdf_text(raw_text))
            if mode in {DebugMode.all, DebugMode.layout}:
                resolved_year = year or extract_emissao_year(pdf_path) or datetime.now().strftime("%y")
                payment_date = extract_invoice_payment_date(pdf_path)
                layout_for_pdf = resolve_layout(payment_date)
                outputs.append(
                    f"layout_resolved={layout_for_pdf.value}, payment_date={payment_date or ''}"
                )
                blocks = extract_blocks_with_layout(pdf_path, layout_for_pdf)
                statements = blocks_to_statements_with_layout(
                    blocks, resolved_year, payment_date, enhanced=enhanced
                )
                if enhanced:
                    outputs.append(
                        "page,column,index,x0,y0,transaction_date,payment_date,description,amount,category,location"
                    )
                else:
                    outputs.append(
                        "page,column,index,x0,y0,transaction_date,payment_date,description,amount"
                    )
                for index, page, column, x0, y0, row in statements:
                    parts = row.split(",", 6)
                    if len(parts) < 5:
                        outputs.append(f"{page},{column},{index},{x0:.2f},{y0:.2f},{row}")
                        continue
                    if enhanced:
                        outputs.append(
                            f"{page},{column},{parts[0]},{x0:.2f},{y0:.2f},{parts[1]},{parts[2]},{parts[3]},{parts[4]},{parts[5] if len(parts) > 5 else ''},{parts[6] if len(parts) > 6 else ''}"
                        )
                    else:
                        outputs.append(
                            f"{page},{column},{parts[0]},{x0:.2f},{y0:.2f},{parts[1]},{parts[2]},{parts[3]},{parts[4]}"
                        )
            if mode in {DebugMode.all, DebugMode.annotate}:
                payment_date = extract_invoice_payment_date(pdf_path)
                layout_for_pdf = resolve_layout(payment_date)
                annotated_path = pdf_path.with_name(f"{pdf_path.stem}_annotated.pdf")
                annotate_pdf_blocks(pdf_path, annotated_path, layout_for_pdf)
                outputs.append(f"annotated_pdf={annotated_path}")
        debug_output = "\n".join(outputs)
        if output is None:
            print(debug_output)
        else:
            output.write_text(debug_output, encoding="utf-8")
        return

    all_rows: list[str] = []
    total_mismatches: list[str] = []
    total_missing: list[str] = []

    manual_total = None
    if total is not None:
        cleaned = total.strip()
        if "," in cleaned:
            manual_total = parse_brl_amount(cleaned)
        else:
            try:
                manual_total = float(cleaned)
            except ValueError as exc:
                raise typer.BadParameter(f"Invalid total: {total}") from exc

    if len(pdf_paths) > 1 and output is not None and not merge:
        raise typer.BadParameter("Use --merge when specifying --output with multiple PDFs.")

    def sort_rows(rows: list[str]) -> list[str]:
        if not sort:
            return rows
        parts = sort.strip().split()
        if len(parts) == 1:
            column, direction = parts[0].lower(), "asc"
        elif len(parts) == 2:
            column, direction = parts[0].lower(), parts[1].lower()
        else:
            raise typer.BadParameter("Sort must be '<column>' or '<column> <ASC|DESC>'.")
        if direction not in {"asc", "desc"}:
            raise typer.BadParameter("Sort direction must be ASC or DESC.")

        valid_columns = {
            "index",
            "transaction_date",
            "payment_date",
            "description",
            "amount",
        }
        if column not in valid_columns:
            raise typer.BadParameter(
                "Sort column must be one of: index, transaction_date, payment_date, description, amount."
            )

        def sort_key(row: str):
            fields = row.split(",", 6)
            if len(fields) < 5:
                return row
            if column == "index":
                return int(fields[0])
            if column == "transaction_date":
                return datetime.strptime(fields[1], "%d/%m/%y")
            if column == "payment_date":
                return datetime.strptime(fields[2], "%d/%m/%y") if fields[2] else datetime.min
            if column == "description":
                return fields[3]
            if column == "amount":
                return float(fields[4])
            return row

        return sorted(rows, key=sort_key, reverse=direction == "desc")

    for pdf_path in pdf_paths:
        resolved_year = year or extract_emissao_year(pdf_path) or datetime.now().strftime("%y")
        payment_date = extract_invoice_payment_date(pdf_path)
        layout_for_pdf = resolve_layout(payment_date)
        text_blocks = extract_blocks(pdf_path, layout_for_pdf)
        statements = blocks_to_statements(
            text_blocks, resolved_year, payment_date, enhanced=enhanced
        )
        expected_total = (
            manual_total if manual_total is not None else extract_total_from_pdf(pdf_path)
        )

        if expected_total is None:
            total_missing.append(str(pdf_path))
        else:
            try:
                check_total(statements, expected_total)
            except ValueError as exc:
                total_mismatches.append(f"{pdf_path}: {exc}")

        rows = flip_sign_last_column(statements)

        if rename:
            last4 = extract_card_last4(pdf_path)
            if not last4:
                raise typer.BadParameter(f"Could not find card last 4 for {pdf_path}.")
            month_info = month_number_for_date(payment_date or "")
            if month_info is None:
                raise typer.BadParameter(
                    f"Could not determine statement month for {pdf_path}."
                )
            year_full, month_number = month_info
            target = pdf_path.with_name(
                f"Itau_{last4}_{year_full}_{month_number}{pdf_path.suffix.lower()}"
            )
            if target != pdf_path:
                if target.exists():
                    raise typer.BadParameter(f"Rename target already exists: {target}")
                pdf_path.rename(target)
                typer.echo(f"Renamed {pdf_path} to {target}")
                pdf_path = target

        if merge:
            all_rows.extend(rows)
        else:
            rows = sort_rows(rows)
            rows = apply_id_schema(rows, locale.value)
            rows = localize_rows(rows, locale.value)
            if output is None:
                per_file_output = pdf_path.with_suffix(".csv")
                headers = CSV_HEADERS_ENHANCED if enhanced else CSV_HEADERS
                write_csv_lines(
                    rows, per_file_output, include_headers=not no_headers, headers=headers
                )
                typer.echo(f"Wrote {len(rows)} rows to {per_file_output}")
            else:
                headers = CSV_HEADERS_ENHANCED if enhanced else CSV_HEADERS
                added = write_csv_lines_idempotent(
                    rows, output, include_headers=not no_headers, headers=headers
                )
                typer.echo(f"Wrote {added} new rows to {output}")

    if merge:
        if sort:
            all_rows = sort_rows(all_rows)
        all_rows = apply_id_schema(all_rows, locale.value)
        all_rows = localize_rows(all_rows, locale.value)
        if output is None:
            headers = CSV_HEADERS_ENHANCED if enhanced else CSV_HEADERS
            write_csv_lines(
                all_rows, output, include_headers=not no_headers, headers=headers
            )
        else:
            headers = CSV_HEADERS_ENHANCED if enhanced else CSV_HEADERS
            added = write_csv_lines_idempotent(
                all_rows, output, include_headers=not no_headers, headers=headers
            )
            typer.echo(f"Wrote {added} new rows to {output}")

    if total_mismatches:
        typer.echo("Warning: total mismatches found:", err=True)
        for message in total_mismatches:
            typer.echo(f"- {message}", err=True)

    if total_missing:
        typer.echo("Warning: totals not found in:", err=True)
        for path in total_missing:
            typer.echo(f"- {path}", err=True)


if __name__ == "__main__":
    app()

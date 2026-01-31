from __future__ import annotations

from pathlib import Path
from datetime import datetime
from enum import Enum
import glob

import typer

from finance_cli.itau import (
    blocks_to_statements,
    blocks_to_statements_with_layout,
    extract_blocks,
    extract_blocks_with_layout,
    extract_total_from_pdf,
    extract_raw_text,
    extract_emissao_year,
    extract_vencimento_date,
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
)
from finance_cli.nu import convert_date_format

app = typer.Typer(help="Personal finance CLI.")


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


@app.command("nu")
def parse_nu(
    csv_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write output to a new CSV instead of in-place."
    ),
) -> None:
    """Normalize Nu CSV date format and flip amounts."""
    out_path = convert_date_format(csv_path, output)
    typer.echo(f"Wrote {out_path}")


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


@app.command("itau")
def parse_itau(
    input_paths: list[str] = typer.Argument(
        ..., help="PDF file, folder, or glob pattern."
    ),
    year: str | None = typer.Option(
        None, "--year", "-y", help="Year in YY format (default: current year)."
    ),
    total: str | None = typer.Option(
        None,
        "--total",
        "-t",
        help="Manual checksum total (e.g. 1234.56 or 1.234,56).",
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
        help="Sort output (format: '<column> <ASC|DESC>').",
    ),
    layout: Layout = typer.Option(
        Layout.modern, "--layout", "-l", help="PDF layout (legacy or modern)."
    ),
    merge: bool = typer.Option(
        False, "--merge", "-m", help="Merge multiple PDFs into one CSV output."
    ),
    locale: Locale = typer.Option(
        Locale.en_us, "--locale", "-L", help="Output locale (en-us or pt-br)."
    ),
    no_headers: bool = typer.Option(
        False, "--no-headers", "-n", help="Do not print CSV headers."
    ),
    enhanced: bool = typer.Option(
        False, "--enhanced", "-e", help="Capture category/location when available."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write output CSV (default: stdout)."
    ),
) -> None:
    """Parse Itaú credit card PDF(s) into CSV lines (id: YYYY-MMM-index)."""
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
                payment_date = extract_vencimento_date(pdf_path)
                blocks = extract_blocks_with_layout(pdf_path, layout)
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
                annotated_path = pdf_path.with_name(f"{pdf_path.stem}_annotated.pdf")
                annotate_pdf_blocks(pdf_path, annotated_path, layout)
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
        payment_date = extract_vencimento_date(pdf_path)
        text_blocks = extract_blocks(pdf_path, layout)
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

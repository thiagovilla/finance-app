from __future__ import annotations

from pathlib import Path
from datetime import datetime
import glob

import typer

from finance_cli.itau import (
    blocks_to_statements,
    extract_blocks,
    extract_total_from_pdf,
    flip_sign_last_column,
    check_total,
    write_csv_lines,
    write_csv_lines_idempotent,
)
from finance_cli.nu import convert_date_format

app = typer.Typer(help="Personal finance CLI.")


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
    input_path: str = typer.Argument(..., help="PDF file, folder, or glob pattern."),
    year: str | None = typer.Option(
        None, "--year", "-y", help="Year in YY format (default: current year)."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write output CSV (default: stdout)."
    ),
) -> None:
    """Parse Itaú credit card PDF(s) into CSV lines."""
    pdf_paths = resolve_itau_inputs(input_path)
    resolved_year = year or datetime.now().strftime("%y")
    all_rows: list[str] = []
    total_mismatches: list[str] = []
    total_missing: list[str] = []

    for pdf_path in pdf_paths:
        text_blocks = extract_blocks(pdf_path)
        statements = blocks_to_statements(text_blocks, resolved_year)
        expected_total = extract_total_from_pdf(pdf_path)

        if expected_total is None:
            total_missing.append(str(pdf_path))
        else:
            try:
                check_total(statements, expected_total)
            except ValueError as exc:
                total_mismatches.append(f"{pdf_path}: {exc}")

        all_rows.extend(flip_sign_last_column(statements))

    if output is None:
        write_csv_lines(all_rows, output)
    else:
        added = write_csv_lines_idempotent(all_rows, output)
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

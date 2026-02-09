import fitz
import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path

from itau_pdf import metadata
from itau_pdf.layout import iter_lines
from itau_pdf.statements import parse_lines
from itau_pdf.debug import annotate_pdf, filter_statement_lines
from finance_cli.utils import resolve_itau_inputs
from core.common import write_statements_csv

app = typer.Typer()
console = Console()


def _process_pdf(pdf_path: Path):
    """Internal helper to parse PDF and return (meta, statements, statement_sum)."""
    with fitz.open(pdf_path) as doc:
        raw_text = "\n".join([page.get_text() for page in doc])
        meta = metadata.get_metadata(raw_text)

        # Validate Metadata fields
        missing = [f for f in ["last4", "total", "payment_date", "issue_date"] if getattr(meta, f) is None]
        if missing:
            raise ValueError(f"Missing metadata: {', '.join(missing)}")

        # Parse Statements
        statements = list(parse_lines(iter_lines(doc), meta.payment_date))
        statement_sum = sum(s.amount for s in statements)

        return meta, statements, statement_sum


@app.command("check")
def check_pdfs(
        glob_pattern: str = typer.Argument(..., help="Glob pattern for Itaú PDFs (e.g. 'faturas/*.pdf')."),
) -> None:
    """Check multiple PDFs for metadata integrity and sum validation."""
    pdf_paths = resolve_itau_inputs(glob_pattern)

    table = Table(title="Itaú PDF Parsing Check")
    table.add_column("File", style="blue")
    table.add_column("Status")
    table.add_column("Details")

    for pdf_path in pdf_paths:
        try:
            meta, statements, stmt_sum = _process_pdf(pdf_path)

            # Check sum
            if round(stmt_sum, 2) != -round(meta.total, 2):
                diff = abs(meta.total + stmt_sum)
                table.add_row(
                    pdf_path.name,
                    "[red]FAIL[/red]",
                    f"Sum mismatch: Meta R$ {meta.total:.2f} vs Stmt R$ {stmt_sum:.2f} (Diff: {diff:.2f})"
                )
            else:
                table.add_row(
                    pdf_path.name,
                    "[green]OK[/green]",
                    f"{len(statements)} txns, R$ {meta.total:.2f}"
                )
        except Exception as e:
            table.add_row(pdf_path.name, "[red]ERROR[/red]", str(e))

    console.print(table)


@app.command("parse")
def parse_pdf(
        glob_pattern: str = typer.Argument(..., help="Path or glob pattern for Itaú PDF files."),
        output: Path | None = typer.Option(None, "--output", "-o", help="Output CSV path."),
        merge: bool = typer.Option(False, "--merge", "-m", help="Merge all PDFs into a single CSV."),
        append: bool = typer.Option(False, "--append", "-a", help="Append to existing CSV."),
) -> None:
    """Parse Itaú PDFs, validate metadata, and export to CSV."""
    pdf_paths = resolve_itau_inputs(glob_pattern)
    if not pdf_paths:
        console.print(f"[red]No files found matching: {glob_pattern}[/red]")
        raise typer.Exit(1)

    all_common_stmts = []
    
    for pdf_path in pdf_paths:
        try:
            meta, statements, statement_sum = _process_pdf(pdf_path)
            
            # Validate Sum
            if round(statement_sum, 2) != -round(meta.total, 2):
                console.print(f"[red]Error in {pdf_path.name}: Sum mismatch (Diff: {abs(meta.total + statement_sum):.2f})[/red]")
                if not merge: continue # Skip this file if not merging

            common_stmts = [s.to_common(meta.payment_date, account=f"itau_{meta.last4}") for s in statements]
            
            if merge:
                all_common_stmts.extend(common_stmts)
            else:
                # Individual processing
                target_output = output or pdf_path.with_suffix(".csv")
                count = write_statements_csv(common_stmts, target_output, append=append)
                console.print(f"[green]Parsed {pdf_path.name}:[/green] {count} statements -> {target_output}")

        except Exception as e:
            console.print(f"[red]Failed to process {pdf_path.name}: {e}[/red]")

    if merge and all_common_stmts:
        target_output = output or Path("merged_statements.csv")
        count = write_statements_csv(all_common_stmts, target_output, append=append)
        console.print(f"[bold green]Merged success![/bold green] Wrote {count} statements to {target_output}")


@app.command("debug")
def debug_itau_pdf(
        pdf_path: Path = typer.Argument(..., help="Itaú PDF to debug."),
        output: Path | None = typer.Option(
            None, "--output", "-o", help="Write debug output to file."
        ),
) -> None:
    """Dump raw text, metadata, lines, statements, and annotated PDF for Itaú PDFs."""
    if not pdf_path.exists():
        console.print(f"[red]Error: File {pdf_path} not found.[/red]")
        raise typer.Exit(1)

    outputs: list[str] = []

    with fitz.open(pdf_path) as doc:
        # 1. Raw Text
        raw_text = "\n".join([page.get_text() for page in doc])
        outputs.append("--- RAW TEXT ---")
        outputs.append(raw_text)

        # 2. Metadata
        outputs.append("\n--- METADATA ---")
        meta = metadata.get_metadata(raw_text)
        outputs.append(f"Card Last 4: {meta.last4}")
        outputs.append(f"Total: {meta.total}")
        outputs.append(f"Payment Date: {meta.payment_date}")
        outputs.append(f"Issue Date: {meta.issue_date}")

        # 3. Lines
        outputs.append("\n--- LINES (RAW) ---")
        for line in iter_lines(doc):
            outputs.append(f"({line.x0:.1f}, {line.y0:.1f}): {line.text}")

        outputs.append("\n--- LINES (STATEMENTS) ---")
        for line in filter_statement_lines(list(iter_lines(doc))):
            outputs.append(f"{line.page} {line.column} {line.text}")

        # 4. Statements
        outputs.append("\n--- STATEMENTS ---")
        # Apply the full processing pipeline for debugging
        for s in parse_lines(iter_lines(doc), meta.payment_date):
            outputs.append(
                f"{s.id} / {s.date} / {s.description} / {s.amount} / {s.category} / {s.location or '-'}"
            )

    # 5. Annotated PDF
    annotate_pdf(str(pdf_path))
    outputs.append(f"\n[Annotated PDF generated for {pdf_path.name}]")

    debug_output = "\n".join(outputs)
    if output is None:
        typer.echo(debug_output)
    else:
        output.write_text(debug_output, encoding="utf-8")
        typer.echo(f"Debug info written to {output}")


if __name__ == "__main__":
    app()

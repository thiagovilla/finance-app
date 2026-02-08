import fitz
import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path

from itau_pdf import metadata
from itau_pdf.layout import iter_lines
from itau_pdf.statements import parse_lines

app = typer.Typer()
console = Console()


@app.command("parse")
def parse_pdf(
        pdf_path: Path = typer.Argument(..., help="Path to the Itaú PDF file."),
) -> None:
    """Parse an Itaú PDF, validate metadata, and check statement sums."""
    if not pdf_path.exists():
        console.print(f"[red]Error: File {pdf_path} not found.[/red]")
        raise typer.Exit(1)

    with fitz.open(pdf_path) as doc:
        raw_text = "\n".join([page.get_text() for page in doc])

        # 1. Get Metadata
        meta = metadata.get_metadata(raw_text)

        # 2. Validate Metadata fields
        missing_fields = []
        if meta.last4 is None: missing_fields.append("last4")
        if meta.total is None: missing_fields.append("total")
        if meta.payment_date is None: missing_fields.append("payment_date")
        if meta.issue_date is None: missing_fields.append("issue_date")

        if missing_fields:
            console.print(f"[red]Error: Missing metadata fields: {', '.join(missing_fields)}[/red]")
            raise typer.Exit(1)

        console.print(
            f"[green]Metadata loaded:[/green] Card: {meta.last4} | Total: R$ {meta.total:.2f} | Due: {meta.payment_date}")

        # 3. Parse Statements
        statements = list(parse_lines(iter_lines(doc), meta.payment_date))

        # 4. Validate Sum
        statement_sum = sum(s.amount for s in statements)
        # Using round to avoid float precision issues in comparison
        if round(statement_sum, 2) != -round(meta.total, 2):
            console.print(
                f"[red]Error: Metadata total (R$ {meta.total:.2f}) does not match statement sum (R$ {statement_sum:.2f}) - Difference: R$ {abs(meta.total - statement_sum):.2f}[/red]")
            raise typer.Exit(1)

        # 5. Print Statements
        table = Table(title=f"Statements for {pdf_path.name}")
        table.add_column("Date", style="cyan")
        table.add_column("Description")
        table.add_column("Amount", justify="right", style="green")
        table.add_column("Category", style="magenta")
        table.add_column("Location", style="yellow")

        for s in statements:
            table.add_row(
                s.date.strftime("%d/%m/%Y"),
                s.description,
                f"{s.amount:.2f}",
                s.category,
                s.location or "-"
            )

        console.print(table)
        console.print(f"\n[bold green]Success![/bold green] Total R$ {-statement_sum:.2f} matches metadata.")


if __name__ == "__main__":
    app()

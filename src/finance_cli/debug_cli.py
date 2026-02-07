from __future__ import annotations
from pathlib import Path
from datetime import datetime
import typer

from finance_cli.cli import resolve_itau_inputs
from finance_cli.itau import get_pdf_text
from itau.layout_blocks import iter_pdf_blocks, Layout as ItauLayout, get_layout
from itau import metadata
from itau.utils import normalize_text

app = typer.Typer(help="Debug entrypoint for personal finance CLI.")

@app.command("itau")
def debug_cli(
        input_path: str = typer.Argument(..., help="Itaú PDF to debug."),
        output: Path | None = typer.Option(
            None, "--output", "-o", help="Write debug output to file."
        ),
) -> None:
    """Dump raw text, normalized text, metadata and layout blocks for Itaú PDFs."""
    pdf_paths = resolve_itau_inputs(input_path)
    outputs: list[str] = []

    for pdf_path in pdf_paths:
        if len(pdf_paths) > 1:
            outputs.append(f"=== {pdf_path} ===")

        # 1. Raw Text
        raw_text = get_pdf_text(pdf_path)
        outputs.append("--- RAW TEXT ---")
        outputs.append(raw_text)

        # 2. Normalized Text
        norm_text = normalize_text(raw_text)
        outputs.append("\n--- NORMALIZED TEXT ---")
        outputs.append(norm_text)

        # 3. Metadata
        outputs.append("\n--- METADATA ---")
        card_last4 = metadata.extract_last4(raw_text)
        stmt_total = metadata.extract_total(raw_text)
        pay_date = metadata.extract_payment_date(raw_text)
        issue_date = metadata.extract_issue_date(raw_text)
        outputs.append(f"Card Last 4: {card_last4}")
        outputs.append(f"Total: {stmt_total}")
        outputs.append(f"Payment Date: {pay_date}")
        outputs.append(f"Issue Date: {issue_date}")

        # 4. List of Lines (using new layout logic)
        outputs.append("\n--- LINES (Layout Blocks) ---")
        for block in iter_pdf_blocks(str(pdf_path), layout=get_layout(issue_date)):
            outputs.append(
                f"[P{block.page} {block.column.value}] ({block.x0:.1f}, {block.y0:.1f}): {block.text}"
            )

    debug_output = "\n".join(outputs)
    if output is None:
        typer.echo(debug_output)
    else:
        output.write_text(debug_output, encoding="utf-8")
        typer.echo(f"Debug info written to {output}")

if __name__ == "__main__":
    app()
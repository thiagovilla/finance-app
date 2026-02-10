from __future__ import annotations

from pathlib import Path
from enum import Enum
import csv
import glob

import typer

from itau_pdf.cli import app as itau_pdf
from cli.category_cli import app as category_cli
from finance_cli.nu import parse_nubank_csv

app = typer.Typer(help="Personal finance CLI.")
app.add_typer(itau_pdf, name="itau_pdf", help="Itaú PDF specific commands.")
app.add_typer(category_cli, name="category", help="Manage transaction categories.")


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


_load_dotenv()


class DebugMode(str, Enum):
    all = "all"
    raw = "raw"
    total = "total"
    normalized = "normalized"
    layout = "layout"
    annotate = "annotate"


class Source(str, Enum):
    itau_cc = "itau_cc"
    nu_cred = "nu_cred"
    nu_acc = "nu_acc"


class Template(str, Enum):
    itau_cc = "itau_cc"
    nu_cred = "nu_cred"
    nu_acc = "nu_acc"


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
            None, "--output", "-o", help="Write output CSV."
        ),
) -> None:
    """Parse Nubank statements. For Itaú, use 'finance itau parse'."""
    resolved_template = template or _detect_template(input_path)

    input_file = Path(input_path)
    if not input_file.exists() or input_file.is_dir():
        raise typer.BadParameter("CSV input must be a file.")
    out_path = parse_nubank_csv(
        input_file,
        output,
        template=resolved_template.value,
    )
    typer.echo(f"Wrote {out_path}")


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
        return Template.nu_acc
    if normalized & {"categoria", "category"}:
        return Template.nu_cred

    name = path.name.lower()
    if any(token in name for token in ["cartao", "card", "cc", "credit", "nu_cred", "nubank_cc"]):
        return Template.nu_cred
    if any(token in name for token in ["conta", "checking", "chk", "account", "nu_acc", "nubank_ca", "nubank_chk"]):
        return Template.nu_acc

    raise typer.BadParameter("Could not auto-detect template; use --template.")


def _detect_source_from_csv(csv_path: Path) -> Source | None:
    source_values = _read_source_column(csv_path)
    if source_values:
        if len(source_values) == 1:
            value = next(iter(source_values))
            try:
                return Source(value)
            except ValueError:
                alias = {"nubank_cc": "nu_cred", "nubank_chk": "nu_acc"}.get(value)
                return Source(alias) if alias else None
        return None

    name = csv_path.name.lower()
    if "itau_pdf" in name:
        return Source.itau_cc
    if "nubank" in name or "nu_" in name or name.startswith("nu"):
        if any(token in name for token in ["conta", "checking", "chk", "account", "nu_acc", "nubank_ca", "nubank_chk"]):
            return Source.nu_acc
        return Source.nu_cred
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


if __name__ == "__main__":
    app()

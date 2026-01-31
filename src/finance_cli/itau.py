from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF

TOTAL_PATTERNS = (
    r"Total\s+desta\s+fatura\s*\n\s*(?:R\$)?\s*([\d\.]+,\d{2})",
    r"O\s+total\s+da\s+sua\s+fatura\s+é:\s*\n?\s*R\$\s*([\d\.]+,\d{2})",
    r"Total\s+da\s+fatura(?!\s+anterior)\s*\n?\s*(?:R\$)?\s*([\d\.]+,\d{2})",
)


def extract_blocks(pdf_path: Path) -> list[str]:
    doc = fitz.open(pdf_path)
    blocks: list[str] = []

    for page in doc:
        for block in page.get_text("blocks"):
            if len(block) < 4:
                continue
            text = block[4].strip()
            if "Compras parceladas" in text:
                doc.close()
                return blocks
            blocks.append(text)

    doc.close()
    return blocks


def parse_brl_amount(value: str) -> float:
    cleaned = value.strip().replace(".", "").replace(",", ".")
    return float(cleaned)


def find_total_in_text(text: str) -> float | None:
    for pattern in TOTAL_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return parse_brl_amount(match.group(1))
    return None


def extract_total_from_pdf(pdf_path: Path) -> float | None:
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return find_total_in_text(text)


def blocks_to_statements(blocks: Iterable[str], year: str) -> list[str]:
    """Process text blocks to extract raw statement entries.

    Each statement pattern: DD/MM, newline, description, newline, price value.
    """
    dd_mm_pattern = re.compile(
        r"(^\d{1,2}/\d{1,2}\n.+\n\s*-?\s*\d+,\d{2}$)", re.MULTILINE
    )
    return [match_to_csv(match, year) for block in blocks for match in dd_mm_pattern.findall(block)]


def match_to_csv(match: str, year: str) -> str:
    """Normalize spacing, decimal separator, and inject year into DD/MM date."""
    match = re.sub(r"\s{2,}", " ", match)
    match = match.replace(",", ".")
    match = match.replace("\n", ",")
    match = re.sub(r"-\s+(?=\d)", "-", match)

    if len(match) > 5:
        match = match[:5] + "/" + year + match[5:]

    return match


def flip_sign_last_column(csv_data: Iterable[str]) -> list[str]:
    new_data = []
    for row in csv_data:
        columns = row.split(",")
        try:
            last_value = float(columns[-1].replace(",", "."))
            columns[-1] = str(last_value * -1)
        except ValueError:
            pass
        new_data.append(",".join(columns))
    return new_data


def check_total(csv_data: Iterable[str], expected_total: float) -> None:
    try:
        total_sum = sum(float(row.split(",")[2]) for row in csv_data)
    except (IndexError, ValueError) as exc:
        raise ValueError("Error parsing numbers from the third column.") from exc

    if round(total_sum, 2) != round(expected_total, 2):
        raise ValueError(
            "Total mismatch: expected {:.2f}, got {:.2f}. Difference: {:.2f}".format(
                expected_total, total_sum, expected_total - total_sum
            )
        )


def write_csv_lines(rows: Iterable[str], output_path: Path | None) -> None:
    if output_path is None:
        for line in rows:
            print(line)
        return

    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        for row in rows:
            writer.writerow(row.split(","))


def load_existing_rows(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()

    with output_path.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        return {",".join(row) for row in reader if row}


def write_csv_lines_idempotent(rows: Iterable[str], output_path: Path) -> int:
    existing_rows = load_existing_rows(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    added = 0
    with output_path.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        for row in rows:
            if row in existing_rows:
                continue
            writer.writerow(row.split(","))
            existing_rows.add(row)
            added += 1
    return added


def parse_itau_pdf(
    pdf_path: Path, year: str | None = None, total: float | None = None
) -> list[str]:
    resolved_year = year or datetime.now().strftime("%y")

    text_blocks = extract_blocks(pdf_path)
    statements = blocks_to_statements(text_blocks, resolved_year)

    if total is not None:
        check_total(statements, total)

    return flip_sign_last_column(statements)

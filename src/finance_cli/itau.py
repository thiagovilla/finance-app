from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF

from itau_pdf.utils import dmy_to_mdy

# this file should be organized like this:
# 1. pdf -> blocks: open PDF, define layout, get metadata, check markers
# 2. blocks -> statements: parse block text into statement objects
# 3. statements -> prepared data: get data ready in memory
# 4. prepared data -> CSV: write data to CSV file

# --------------- CONSTANTS & TYPES ---------------

CSV_HEADERS = ["id", "transaction_date", "payment_date", "description", "amount", "acc"]
MONTH_ABBREVIATIONS = [
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
]

def get_pdf_text(pdf_path: str) -> str:
    """Extracts all text from a PDF file."""
    with fitz.open(pdf_path) as pdf:
        return "\n".join(page.get_text() for page in pdf)

# --------------- FORMATTING & ID GENERATION (ADR 0004) ---------------

def _generate_itau_id(date_str: str, index: int) -> str:
    """Generates a deterministic ID: YYYY-MMM-index."""
    try:
        parsed = datetime.strptime(date_str, "%d/%m/%y")
        year = parsed.strftime("%Y")
        month = MONTH_ABBREVIATIONS[parsed.month - 1]
    except ValueError:
        year = "0000"
        month = "UNK"
    return f"{year}-{month}-{index}"


def _match_to_csv(match: str, year: str) -> str:
    """Normalize spacing, decimal separator, and inject year into DD/MM date."""
    lines = match.splitlines()
    if len(lines) >= 3:
        date_line = re.sub(r"\s+", "", lines[0])
        date_match = re.match(r"^(\d{1,2})/(\d{1,2})$", date_line)
        if date_match:
            date_part = f"{date_match.group(1)}/{date_match.group(2)}/{year}"
            description = re.sub(r"\s{2,}", " ", lines[1]).strip()
            amount_line = lines[2]
            if len(lines) >= 4:
                installment = re.sub(r"\s+", "", lines[2])
                if re.match(r"^\d{1,2}/\d{1,2}$", installment):
                    description = f"{description} {installment}"
                    amount_line = lines[3]
            amount = re.sub(r"\s+", "", amount_line).replace(",", ".")
            amount = re.sub(r"-\s+(?=\d)", "-", amount)
            return f"{date_part},{description},{amount}"
    return match.replace("\n", ",")


def _localize_rows(rows: Iterable[str]) -> list[str]:
    """Standardizes dates to MM/DD/YY for the final CSV output."""
    localized: list[str] = []
    for row in rows:
        parts = row.split(",")
        if len(parts) < 6:
            localized.append(row)
            continue
        row_id, txn_date, pay_date, desc, amount, acc = parts[:6]
        extra = parts[6:]
        localized.append(",".join([row_id, dmy_to_mdy(txn_date), dmy_to_mdy(pay_date), desc, amount, acc] + extra))
    return localized


def _flip_sign_last_column(csv_data: Iterable[str]) -> list[str]:
    """Flips amount sign (spending is negative in DB, but often positive in PDFs)."""
    new_data = []
    for row in csv_data:
        columns = row.split(",")
        if len(columns) < 5:
            new_data.append(row)
            continue
        try:
            amount_value = float(columns[4])
            columns[4] = f"{amount_value * -1:.2f}"
        except ValueError:
            pass
        new_data.append(",".join(columns))
    return new_data


# --------------- METADATA EXTRACTION ---------------

def _normalize_amount_text(amount: str) -> str | None:
    cleaned = re.sub(r"\s+", "", amount)
    if not re.match(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$", cleaned) and not re.match(r"^-?\d+,\d{2}$", cleaned):
        return None
    return cleaned.replace(".", "").replace(",", ".")


# this is definitely control flow, not lib
def check_total(csv_data: Iterable[str], expected_total: float) -> None:
    try:
        total_sum = sum(float(row.split(",")[4]) for row in csv_data)
        if round(total_sum, 2) != round(expected_total, 2):
            raise ValueError(f"Total mismatch: expected {expected_total:.2f}, got {total_sum:.2f}")
    except (IndexError, ValueError) as exc:
        raise ValueError("Error validating totals.") from exc


# --------------- I/O & IDEMPOTENCY ---------------

def write_csv_lines_idempotent(rows: Iterable[str], output_path: Path, include_headers: bool = True,
                               headers: list[str] | None = None) -> int:
    headers = headers or CSV_HEADERS
    existing_ids = set()
    if output_path.exists():
        with output_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                existing_ids = {r["id"] for r in reader if "id" in r}

    added = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if output_path.exists() else "w"
    with output_path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if mode == "w" and include_headers:
            writer.writerow(headers)
        for row in rows:
            parts = row.split(",")
            if parts[0] not in existing_ids:
                writer.writerow(parts)
                existing_ids.add(parts[0])
                added += 1
    return added

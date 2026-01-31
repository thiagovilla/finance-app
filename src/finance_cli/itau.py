from __future__ import annotations

import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF

TOTAL_PATTERNS = (
    r"Total\s+desta\s+fatura\s*\n\s*(?:R\$)?\s*([\d\.]+,\d{2})",
    r"O\s+total\s+da\s+sua\s+fatura\s+é:\s*\n?\s*R\$\s*([\d\.]+,\d{2})",
    r"Total\s+da\s+fatura(?!\s+anterior)\s*\n?\s*(?:R\$)?\s*([\d\.]+,\d{2})",
)
CSV_HEADERS = ["index", "transaction_date", "payment_date", "description", "amount"]


def extract_blocks(pdf_path: Path) -> list[str]:
    doc = fitz.open(pdf_path)
    blocks: list[str] = []

    for page in doc:
        for block in page.get_text("blocks"):
            if len(block) < 4:
                continue
            text = block[4].strip()
            normalized = unicodedata.normalize("NFKD", re.sub(r"\s+", "", text))
            normalized = "".join(
                char for char in normalized if not unicodedata.combining(char)
            ).lower()
            if "comprasparceladas" in normalized:
                doc.close()
                return blocks
            blocks.append(text)

    doc.close()
    return blocks


def parse_brl_amount(value: str) -> float:
    cleaned = value.strip().replace(".", "").replace(",", ".")
    return float(cleaned)


def format_date_for_locale(date_str: str, locale: str) -> str:
    if not date_str:
        return date_str
    try:
        parsed = datetime.strptime(date_str, "%d/%m/%y")
    except ValueError:
        return date_str
    if locale == "pt-br":
        return parsed.strftime("%d/%m/%y")
    return parsed.strftime("%m/%d/%y")


def format_amount_for_locale(amount_str: str, locale: str) -> str:
    if locale == "pt-br":
        return amount_str.replace(".", ",")
    return amount_str


def find_total_in_text(text: str) -> float | None:
    """Extracts total amount from text using regex patterns"""
    for pattern in TOTAL_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return parse_brl_amount(match.group(1))

    normalized_text = normalize_pdf_text(text)
    labels = ("ototaldasuafaturae", "totaldestafatura")
    for label in labels:
        match = re.search(
            rf"{label}.{{0,200}}?(?:r\$)?([\d.]+,\d{{2}})",
            normalized_text,
            flags=re.DOTALL,
        )
        if match:
            return parse_brl_amount(match.group(1))
    return None


def normalize_pdf_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).lower()
    return re.sub(r"\s+", "", normalized)


def extract_total_from_pdf(pdf_path: Path) -> float | None:
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return find_total_in_text(text)


def extract_raw_text(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    text = "\n\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def extract_emissao_year(pdf_path: Path) -> str | None:
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    match = re.search(r"Emiss[aã]o:\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%d/%m/%Y").strftime("%y")
    except ValueError:
        return None


def extract_vencimento_date(pdf_path: Path) -> str | None:
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    match = re.search(r"Vencimento:\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%d/%m/%Y").strftime("%d/%m/%y")
    except ValueError:
        return None


def blocks_to_statements(
    blocks: Iterable[str], year: str, payment_date: str | None
) -> list[str]:
    """Process text blocks to extract raw statement entries.

    Each statement pattern: DD/MM, newline, description, newline, price value.
    """
    dd_mm_pattern = re.compile(
        r"(^[\d\s]{1,2}/[\d\s]{1,2}\n.+\n(?:[\d\s]{1,2}/[\d\s]{1,2}\n)?\s*-?\s*\d+,\d{2}$)",
        re.MULTILINE,
    )
    statements: list[str] = []
    index = 0
    for block in blocks:
        normalized_block = re.sub(
            r"(?m)^(\d{1,2})/(\d)\s+(\d)$",
            r"\1/\2\3",
            block,
        )
        for match in dd_mm_pattern.findall(normalized_block):
            payment_field = payment_date or ""
            date_part, description, amount = match_to_csv(match, year).split(",", 2)
            statements.append(
                f"{index},{date_part},{payment_field},{description},{amount}"
            )
            index += 1
    return statements


def match_to_csv(match: str, year: str) -> str:
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


def localize_rows(rows: Iterable[str], locale: str) -> list[str]:
    localized: list[str] = []
    for row in rows:
        parts = row.split(",", 4)
        if len(parts) != 5:
            localized.append(row)
            continue
        index, transaction_date, payment_date, description, amount = parts
        transaction_date = format_date_for_locale(transaction_date, locale)
        payment_date = format_date_for_locale(payment_date, locale)
        amount = format_amount_for_locale(amount, locale)
        localized.append(
            ",".join([index, transaction_date, payment_date, description, amount])
        )
    return localized


def check_total(csv_data: Iterable[str], expected_total: float) -> None:
    try:
        total_sum = sum(float(row.split(",")[4]) for row in csv_data)
    except (IndexError, ValueError) as exc:
        raise ValueError("Error parsing numbers from the fifth column.") from exc

    if round(total_sum, 2) != round(expected_total, 2):
        raise ValueError(
            "Total mismatch: expected {:.2f}, got {:.2f}. Difference: {:.2f}".format(
                expected_total, total_sum, expected_total - total_sum
            )
        )


def write_csv_lines(
    rows: Iterable[str], output_path: Path | None, include_headers: bool = True
) -> None:
    if output_path is None:
        if include_headers:
            print(",".join(CSV_HEADERS))
        for line in rows:
            print(line)
        return

    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if include_headers:
            writer.writerow(CSV_HEADERS)
        for row in rows:
            writer.writerow(row.split(","))


def load_existing_rows(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()

    with output_path.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        return {
            ",".join(row)
            for row in reader
            if row and row != CSV_HEADERS
        }


def write_csv_lines_idempotent(
    rows: Iterable[str], output_path: Path, include_headers: bool = True
) -> int:
    existing_rows = load_existing_rows(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    added = 0
    with output_path.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if include_headers and (not output_path.exists() or output_path.stat().st_size == 0):
            writer.writerow(CSV_HEADERS)
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
    resolved_year = year or extract_emissao_year(pdf_path) or datetime.now().strftime("%y")
    payment_date = extract_vencimento_date(pdf_path)

    text_blocks = extract_blocks(pdf_path)
    statements = blocks_to_statements(text_blocks, resolved_year, payment_date)

    if total is not None:
        check_total(statements, total)

    return flip_sign_last_column(statements)

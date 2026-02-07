from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF

from itau.utils import dmy_to_mdy

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


# --------------- 1. PDF PARSING ---------------

# Goal: Open PDF, define layout, get metadata, check markers

# 1. Open PDF and extract all text
# 2. Find metadata (last 4 digits, total, payment date)
# 3. Split content left/right columns
# 4. Parse blocks in order (inverted N) between start and stop markers

# --------------- 1.1 INVOICE METADATA ---------------

def get_pdf_text(pdf_path: str) -> str:
    """Extracts all text from a PDF file."""
    with fitz.open(pdf_path) as pdf:
        return "\n".join(page.get_text() for page in pdf)


## FROM NOW ON STATAMENTS


# @dataclass(frozen=True)
# class Statement:
#     date: datetime
#     amount: float
#     description: str
#
#
# def _parse_block(block: BlockInfo) -> List[Statement] | None:
#     return None


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


# --------------- STATEMENT EXTRACTION ---------------

def _blocks_to_statements(blocks: Iterable[str], year: str, payment_date: str | None) -> list[str]:
    statements: list[str] = []
    index = 1
    for block in blocks:
        parsed, index = _parse_block_basic(block, year, payment_date, index)
        statements.extend(parsed)
    return statements


def _parse_block_basic(block: str, year: str, payment_date: str | None, index: int) -> tuple[list[str], int]:
    normalized_block = re.sub(r"(?m)^(\d{1,2})/(\d)\s+(\d)$", r"\1/\2\3", block)
    lines = [line for line in normalized_block.splitlines() if line.strip()]
    output_rows: list[str] = []
    i = 0
    while i < len(lines):
        date_line = re.sub(r"\s+", "", lines[i])
        if not re.match(r"^\d{1,2}/\d{1,2}$", date_line):
            i += 1
            continue
        j, desc_lines, inst_line, amt_line = i + 1, [], None, None
        while j < len(lines):
            line = lines[j].strip()
            amt = _normalize_amount_text(line)
            if amt:
                amt_line = amt
                break
            if re.match(r"^\d{1,2}/\d{1,2}$", re.sub(r"\s+", "", line)) and j + 1 < len(lines):
                next_amt = _normalize_amount_text(lines[j + 1])
                if next_amt:
                    inst_line, amt_line = re.sub(r"\s+", "", line), next_amt
                    j += 1
                    break
            desc_lines.append(line)
            j += 1
        if amt_line and desc_lines:
            match = f"{date_line}\n{' '.join(desc_lines)}\n{inst_line or ''}\n{amt_line}".replace("\n\n", "\n")
            d_part, desc, amt = _match_to_csv(match, year).split(",", 2)
            row_id = _generate_itau_id(payment_date or d_part, index)
            output_rows.append(f"{row_id},{d_part},{payment_date or ''},{desc},{amt},itau_cc")
            index, i = index + 1, j + 1
        else:
            i += 1
    return output_rows, index


# --------------- METADATA EXTRACTION ---------------

def _normalize_amount_text(amount: str) -> str | None:
    cleaned = re.sub(r"\s+", "", amount)
    if not re.match(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$", cleaned) and not re.match(r"^-?\d+,\d{2}$", cleaned):
        return None
    return cleaned.replace(".", "").replace(",", ".")


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


# def _extract_blocks(pdf_path: Path, layout: Layout = Layout.modern) -> list[str]:
#     """Extract text blocks from a PDF layout, stopping at the installment marker."""
#     blocks: list[str] = []
#     for _, page_blocks, marker in _iter_page_blocks(pdf_path, layout):
#         left_marker_y = marker["left"]
#         right_marker_y = marker["right"]
#
#         def should_include(col: str, y0: float) -> bool:
#             if col == "left" and left_marker_y is not None:
#                 return y0 < left_marker_y
#             if col == "right" and right_marker_y is not None:
#                 return y0 < right_marker_y
#             return True
#
#         left_blocks = sorted(
#             (
#                 (y0, x0, text)
#                 for col, y0, x0, _, _, text in page_blocks
#                 if col == "left" and should_include(col, y0)
#             ),
#             key=lambda item: (item[0], item[1]),
#         )
#         if left_marker_y is not None:
#             right_blocks: list[tuple[float, float, str]] = []
#         else:
#             right_blocks = sorted(
#                 (
#                     (y0, x0, text)
#                     for col, y0, x0, _, _, text in page_blocks
#                     if col == "right" and should_include(col, y0)
#                 ),
#                 key=lambda item: (item[0], item[1]),
#             )
#
#         for _, _, text in left_blocks + right_blocks:
#             blocks.append(text)
#
#         if left_marker_y is not None or right_marker_y is not None:
#             return blocks
#
#     return blocks


# def extract_blocks_with_layout(
#         pdf_path: Path, layout: Layout = Layout.modern
# ) -> list[BlockInfo]:
#     """Extract text blocks with page/column metadata for a layout."""
#     blocks: list[BlockInfo] = []
#     for page_number, page_blocks, marker in _iter_page_blocks(pdf_path, layout):
#         left_marker_y = marker["left"]
#         right_marker_y = marker["right"]
#
#         def should_include(col: str, y0: float) -> bool:
#             if col == "left" and left_marker_y is not None:
#                 return y0 < left_marker_y
#             if col == "right" and right_marker_y is not None:
#                 return y0 < right_marker_y
#             return True
#
#         left_blocks = sorted(
#             (
#                 (y0, x0, text)
#                 for col, y0, x0, _, _, text in page_blocks
#                 if col == "left" and should_include(col, y0)
#             ),
#             key=lambda item: (item[0], item[1]),
#         )
#         if left_marker_y is not None:
#             right_blocks: list[tuple[float, float, str]] = []
#         else:
#             right_blocks = sorted(
#                 (
#                     (y0, x0, text)
#                     for col, y0, x0, _, _, text in page_blocks
#                     if col == "right" and should_include(col, y0)
#                 ),
#                 key=lambda item: (item[0], item[1]),
#             )
#
#         for y0, x0, text in left_blocks:
#             blocks.append(
#                 BlockInfo(
#                     page=page_number,
#                     column="left",
#                     y0=y0,
#                     x0=x0,
#                     text=text,
#                 )
#             )
#         for y0, x0, text in right_blocks:
#             blocks.append(
#                 BlockInfo(
#                     page=page_number,
#                     column="right",
#                     y0=y0,
#                     x0=x0,
#                     text=text,
#                 )
#             )
#
#         if left_marker_y is not None or right_marker_y is not None:
#             break
#     return blocks


# --------------- DEBUG ---------------

# def annotate_pdf_blocks(
#         pdf_path: Path, output_path: Path, layout: Layout = Layout.modern
# ) -> Path:
#     """Write an annotated PDF with line rectangles and coordinates for a layout."""
#     doc = fitz.open(pdf_path)
#     for page_number, page, split_x in _iter_pages(doc, layout):
#         page_rect = page.rect
#         page.draw_line(
#             fitz.Point(split_x, page_rect.y0),
#             fitz.Point(split_x, page_rect.y1),
#             color=(0, 0.6, 0),
#             width=0.5,
#         )
#         page.insert_text(
#             fitz.Point(split_x + 2, page_rect.y0 + 8),
#             f"split_x={split_x:.2f}",
#             fontsize=7,
#             color=(0, 0.6, 0),
#         )
#         page_lines = _extract_page_lines(page, split_x)
#         for column, lines in page_lines.items():
#             color = (1, 0, 0) if column == "right" else (0, 0, 1)
#             for line in lines:
#                 rect = fitz.Rect(line.x0, line.y0, line.x1, line.y1)
#                 page.draw_rect(rect, color=color, width=0.5)
#                 label = f"{line.x0:.2f},{line.y0:.2f}"
#                 page.insert_text(
#                     fitz.Point(line.x0, max(line.y0 - 4, page_rect.y0 + 6)),
#                     label,
#                     fontsize=6,
#                     color=color,
#                 )
#     doc.save(output_path)
#     doc.close()
#     return output_path


# This is debug
# def _apply_marker(
#         page_lines: dict[str, list[Line]],
#         marker: dict[str, float | None],
# ) -> tuple[list[Line], list[Line]]:
#     left_lines = page_lines["left"]
#     right_lines = page_lines["right"]
#     if marker.get("start_left") is not None:
#         left_lines = [line for line in left_lines if line.y0 > marker["start_left"]]
#     if marker.get("start_right") is not None:
#         right_lines = [line for line in right_lines if line.y0 > marker["start_right"]]
#     if marker["left"] is not None:
#         left_lines = [line for line in left_lines if line.y0 < marker["left"]]
#         right_lines = []
#     elif marker["right"] is not None:
#         right_lines = [line for line in right_lines if line.y0 < marker["right"]]
#     return left_lines, right_lines


# def _parse_statements_from_lines(
#         lines: list[Line],
#         page_number: int,
#         column: str,
#         year: str,
#         payment_date: str | None,
#         statements: list[tuple[int, int, str, float, float, str]],
#         index: int,
# ) -> int:
#     i = 0
#     while i < len(lines):
#         date_line = lines[i]
#         date_text = re.sub(r"\s+", "", date_line.text)
#         if not re.match(r"^\d{1,2}/\d{1,2}$", date_text):
#             i += 1
#             continue
#         j = i + 1
#         while j < len(lines) and not lines[j].text.strip():
#             j += 1
#         if j >= len(lines):
#             break
#         desc_line = lines[j]
#         k = j + 1
#         while k < len(lines) and not lines[k].text.strip():
#             k += 1
#         if k >= len(lines):
#             break
#         installment_line = None
#         amount_line = lines[k]
#         installment_text = re.sub(r"\s+", "", amount_line.text)
#         if re.match(r"^\d{1,2}/\d{1,2}$", installment_text):
#             installment_line = amount_line
#             k += 1
#             if k >= len(lines):
#                 break
#             amount_line = lines[k]
#         amount_text = _normalize_amount_text(amount_line.text)
#         if amount_text is None:
#             i += 1
#             continue
#         if installment_line is None:
#             match = f"{date_text}\n{desc_line.text}\n{amount_text}"
#         else:
#             match = f"{date_text}\n{desc_line.text}\n{installment_text}\n{amount_text}"
#         date_part, description, amount = _match_to_csv(match, year).split(",", 2)
#         payment_field = payment_date or ""
#         # Generate deterministic ID here according to ADR 0004
#         row_id = _generate_itau_id(payment_field or date_part, index)
#         row = f"{row_id},{date_part},{payment_field},{description},{amount},itau_cc"
#         statements.append((index, page_number, column, date_line.x0, date_line.y0, row))
#         index += 1
#         i = k + 1
#     return index


def _normalize_amount_text(amount: str) -> str | None:
    """Normalize amount text by removing whitespace and checking format."""
    cleaned = re.sub(r"\s+", "", amount)
    if not cleaned:
        return None
    if not re.match(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$", cleaned) and not re.match(
            r"^-?\d+,\d{2}$", cleaned
    ):
        return None
    return cleaned.replace(".", "")


def _parse_block_with_metadata(
        block: str, year: str, payment_date: str | None, index: int
) -> tuple[list[str], int]:
    normalized_block = re.sub(
        r"(?m)^(\d{1,2})/(\d)\s+(\d)$",
        r"\1/\2\3",
        block,
    )
    lines = [line for line in normalized_block.splitlines() if line.strip()]
    statements: list[dict[str, str | None]] = []
    pending: list[int] = []
    current: dict[str, str | None] | None = None
    i = 0
    while i < len(lines):
        raw_line = lines[i].strip()
        normalized = re.sub(r"\s+", "", raw_line)
        if re.match(r"^\d{1,2}/\d{1,2}$", normalized):
            if current and not current.get("amount"):
                current = None
            if current is None:
                current = {
                    "date": normalized,
                    "desc": "",
                    "installment": None,
                    "amount": None,
                    "category": "",
                    "location": "",
                }
            i += 1
            continue

        if current and not current.get("amount"):
            amount_text = _normalize_amount_text(raw_line)
            if amount_text is not None:
                current["amount"] = amount_text
                statements.append(current)
                pending.append(len(statements) - 1)
                current = None
                i += 1
                continue

            if re.match(r"^\d{1,2}/\d{1,2}$", normalized):
                k = i + 1
                while k < len(lines) and not lines[k].strip():
                    k += 1
                if k < len(lines):
                    amount_text = _normalize_amount_text(lines[k])
                    if amount_text is not None:
                        current["installment"] = normalized
                        current["amount"] = amount_text
                        statements.append(current)
                        pending.append(len(statements) - 1)
                        current = None
                        i = k + 1
                        continue

            current["desc"] = (
                f"{current['desc']} {raw_line}".strip()
                if current["desc"]
                else raw_line
            )
            i += 1
            continue

        if pending:
            if len(raw_line.split()) >= 2:
                parts = raw_line.rsplit(" ", 1)
                category = parts[0].strip()
                location = parts[1].strip()
                stmt_index = pending.pop(0)
                statements[stmt_index]["category"] = category
                statements[stmt_index]["location"] = location
            i += 1
            continue

        i += 1

    output_rows: list[str] = []
    for statement in statements:
        if not statement.get("amount") or not statement.get("desc") or not statement.get("date"):
            continue
        date_line = statement["date"] or ""
        desc_line = statement["desc"] or ""
        installment_line = statement["installment"]
        amount_line = statement["amount"] or ""
        if installment_line:
            match = f"{date_line}\n{desc_line}\n{installment_line}\n{amount_line}"
        else:
            match = f"{date_line}\n{desc_line}\n{amount_line}"
        payment_field = payment_date or ""
        date_part, description, amount = _match_to_csv(match, year).split(",", 2)
        category = statement["category"] or ""
        location = statement["location"] or ""
        row_id = _generate_itau_id(payment_field or date_part, index)
        output_rows.append(
            f"{row_id},{date_part},{payment_field},{description},{amount},itau_cc,{category},{location}"
        )
        index += 1
    return output_rows, index

# def _iter_page_blocks(
#         pdf_path: Path,
#         layout: Layout = Layout.modern,
# ) -> Iterable[
#     tuple[int, list[tuple[str, float, float, float, float, str]], dict[str, float | None]]
# ]:
#     """Yield per-page blocks using the layout split."""
#     start_marker = _normalize_text("lançamentos: compras e saques")
#     doc = fitz.open(pdf_path)
#     for page_number, page, split_x in _iter_pages(doc, layout):
#         page_lines = _extract_page_lines(page, split_x)
#         marker = {
#             "left": None,
#             "right": None,
#             "start_left": None,
#             "start_right": None,
#         }
#         for column, lines in page_lines.items():
#             for line in lines:
#                 normalized = _normalize_text(line.text)
#                 if layout == Layout.modern and marker[f"start_{column}"] is None:
#                     if start_marker in normalized:
#                         marker[f"start_{column}"] = line.y0
#                 if "comprasparceladas" in normalized:
#                     marker[column] = line.y0
#                     break
#
#         left_rect = fitz.Rect(page.rect.x0, page.rect.y0, split_x, page.rect.y1)
#         right_rect = fitz.Rect(split_x, page.rect.y0, page.rect.x1, page.rect.y1)
#         page_blocks: list[tuple[str, float, float, float, float, str]] = []
#
#         for column, rect in (("left", left_rect), ("right", right_rect)):
#             for block in page.get_text("blocks", clip=rect):
#                 if len(block) < 5:
#                     continue
#                 text = block[4].strip()
#                 if not text:
#                     continue
#                 x0, y0, x1, y1 = block[0], block[1], block[2], block[3]
#                 start_y = marker.get(f"start_{column}")
#                 end_y = marker.get(column)
#                 if start_y is not None and y0 <= start_y:
#                     continue
#                 if end_y is not None and y0 >= end_y:
#                     continue
#                 page_blocks.append((column, y0, x0, x1, y1, text))
#
#         yield page_number, page_blocks, marker
#         if marker["left"] is not None or marker["right"] is not None:
#             break
#     doc.close()


# --------------- LAST 4 ---------------

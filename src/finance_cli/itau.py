from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF

TOTAL_PATTERNS = (
    r"Total\s+desta\s+fatura\s*\n\s*(?:R\$)?\s*([\d\.]+,\d{2})",
    r"O\s+total\s+da\s+sua\s+fatura\s+é:\s*\n?\s*R\$\s*([\d\.]+,\d{2})",
    r"Total\s+da\s+fatura(?!\s+anterior)\s*\n?\s*(?:R\$)?\s*([\d\.]+,\d{2})",
)
CSV_HEADERS = ["id", "transaction_date", "payment_date", "description", "amount"]
CSV_HEADERS_ENHANCED = CSV_HEADERS + ["category", "location"]
EN_US_MONTH_ABBREVIATIONS = [
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
]

class Layout(str, Enum):
    legacy = "legacy"
    modern = "modern"


@dataclass(frozen=True)
class BlockInfo:
    page: int
    column: str
    y0: float
    x0: float
    text: str


@dataclass(frozen=True)
class LineInfo:
    y0: float
    x0: float
    y1: float
    x1: float
    text: str


def extract_blocks(pdf_path: Path, layout: Layout = Layout.modern) -> list[str]:
    """Extract text blocks from a PDF layout, stopping at the installment marker."""
    blocks: list[str] = []
    for _, page_blocks, marker in _iter_page_blocks(pdf_path, layout):
        left_marker_y = marker["left"]
        right_marker_y = marker["right"]

        def should_include(col: str, y0: float) -> bool:
            if col == "left" and left_marker_y is not None:
                return y0 < left_marker_y
            if col == "right" and right_marker_y is not None:
                return y0 < right_marker_y
            return True

        left_blocks = sorted(
            (
                (y0, x0, text)
                for col, y0, x0, _, _, text in page_blocks
                if col == "left" and should_include(col, y0)
            ),
            key=lambda item: (item[0], item[1]),
        )
        if left_marker_y is not None:
            right_blocks: list[tuple[float, float, str]] = []
        else:
            right_blocks = sorted(
                (
                    (y0, x0, text)
                    for col, y0, x0, _, _, text in page_blocks
                    if col == "right" and should_include(col, y0)
                ),
                key=lambda item: (item[0], item[1]),
            )

        for _, _, text in left_blocks + right_blocks:
            blocks.append(text)

        if left_marker_y is not None or right_marker_y is not None:
            return blocks

    return blocks


def extract_blocks_with_layout(
    pdf_path: Path, layout: Layout = Layout.modern
) -> list[BlockInfo]:
    """Extract text blocks with page/column metadata for a layout."""
    blocks: list[BlockInfo] = []
    for page_number, page_blocks, marker in _iter_page_blocks(pdf_path, layout):
        left_marker_y = marker["left"]
        right_marker_y = marker["right"]

        def should_include(col: str, y0: float) -> bool:
            if col == "left" and left_marker_y is not None:
                return y0 < left_marker_y
            if col == "right" and right_marker_y is not None:
                return y0 < right_marker_y
            return True

        left_blocks = sorted(
            (
                (y0, x0, text)
                for col, y0, x0, _, _, text in page_blocks
                if col == "left" and should_include(col, y0)
            ),
            key=lambda item: (item[0], item[1]),
        )
        if left_marker_y is not None:
            right_blocks: list[tuple[float, float, str]] = []
        else:
            right_blocks = sorted(
                (
                    (y0, x0, text)
                    for col, y0, x0, _, _, text in page_blocks
                    if col == "right" and should_include(col, y0)
                ),
                key=lambda item: (item[0], item[1]),
            )

        for y0, x0, text in left_blocks:
            blocks.append(
                BlockInfo(
                    page=page_number,
                    column="left",
                    y0=y0,
                    x0=x0,
                    text=text,
                )
            )
        for y0, x0, text in right_blocks:
            blocks.append(
                BlockInfo(
                    page=page_number,
                    column="right",
                    y0=y0,
                    x0=x0,
                    text=text,
                )
            )

        if left_marker_y is not None or right_marker_y is not None:
            break
    return blocks


def annotate_pdf_blocks(
    pdf_path: Path, output_path: Path, layout: Layout = Layout.modern
) -> Path:
    """Write an annotated PDF with line rectangles and coordinates for a layout."""
    doc = fitz.open(pdf_path)
    for page_number, page, split_x in _iter_pages_with_split(doc, layout):
        page_rect = page.rect
        page.draw_line(
            fitz.Point(split_x, page_rect.y0),
            fitz.Point(split_x, page_rect.y1),
            color=(0, 0.6, 0),
            width=0.5,
        )
        page.insert_text(
            fitz.Point(split_x + 2, page_rect.y0 + 8),
            f"split_x={split_x:.2f}",
            fontsize=7,
            color=(0, 0.6, 0),
        )
        page_lines = _extract_page_lines(page, split_x)
        for column, lines in page_lines.items():
            color = (1, 0, 0) if column == "right" else (0, 0, 1)
            for line in lines:
                rect = fitz.Rect(line.x0, line.y0, line.x1, line.y1)
                page.draw_rect(rect, color=color, width=0.5)
                label = f"{line.x0:.2f},{line.y0:.2f}"
                page.insert_text(
                    fitz.Point(line.x0, max(line.y0 - 4, page_rect.y0 + 6)),
                    label,
                    fontsize=6,
                    color=color,
                )
    doc.save(output_path)
    doc.close()
    return output_path


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", re.sub(r"\s+", "", text))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return normalized.lower()


def _compute_split_x(words: list[tuple], page_rect: fitz.Rect) -> float:
    x0_values = sorted(word[0] for word in words)
    if len(x0_values) < 2:
        return page_rect.x0 + (page_rect.width / 2)
    max_gap = 0.0
    split_x = page_rect.x0 + (page_rect.width / 2)
    prev = x0_values[0]
    for current in x0_values[1:]:
        gap = current - prev
        if gap > max_gap:
            max_gap = gap
            split_x = (prev + current) / 2
        prev = current
    min_x0 = x0_values[0]
    max_x0 = x0_values[-1]
    span = max_x0 - min_x0
    if span <= 0:
        return page_rect.x0 + (page_rect.width / 2)
    min_split = min_x0 + (span * 0.25)
    max_split = max_x0 - (span * 0.25)
    if max_gap >= 20.0 and min_split <= split_x <= max_split:
        return split_x
    return min_x0 + (span / 2)


def _group_words_into_lines(words: list[tuple], y_tol: float | None = None) -> list[LineInfo]:
    if not words:
        return []
    if y_tol is None:
        heights = sorted(word[3] - word[1] for word in words)
        median_height = heights[len(heights) // 2]
        y_tol = max(2.0, median_height * 0.3)
    words_sorted = sorted(words, key=lambda w: (w[1], w[0]))
    lines: list[dict] = []
    for word in words_sorted:
        x0, y0, x1, y1, text = word[0], word[1], word[2], word[3], word[4]
        if not lines or abs(y0 - lines[-1]["y0"]) > y_tol:
            lines.append(
                {
                    "y0": y0,
                    "y1": y1,
                    "words": [(x0, y0, x1, y1, text)],
                }
            )
        else:
            lines[-1]["y0"] = min(lines[-1]["y0"], y0)
            lines[-1]["y1"] = max(lines[-1]["y1"], y1)
            lines[-1]["words"].append((x0, y0, x1, y1, text))
    result: list[LineInfo] = []
    for line in lines:
        word_items = sorted(line["words"], key=lambda w: w[0])
        text = " ".join(word[4] for word in word_items).strip()
        if not text:
            continue
        x0 = min(word[0] for word in word_items)
        x1 = max(word[2] for word in word_items)
        result.append(LineInfo(y0=line["y0"], x0=x0, y1=line["y1"], x1=x1, text=text))
    return result


def _extract_page_lines(page: fitz.Page, split_x: float) -> dict[str, list[LineInfo]]:
    words = page.get_text("words")
    if not words:
        return {"left": [], "right": []}
    left_words: list[tuple] = []
    right_words: list[tuple] = []
    for word in words:
        if word[0] < split_x:
            left_words.append(word)
        else:
            right_words.append(word)
    return {
        "left": _group_words_into_lines(left_words),
        "right": _group_words_into_lines(right_words),
    }


def _iter_page_lines(
    pdf_path: Path,
    layout: Layout = Layout.modern,
) -> Iterable[tuple[int, dict[str, list[LineInfo]], dict[str, float | None]]]:
    """Yield per-page lines using the layout split."""
    start_marker = _normalize_text("lançamentos: compras e saques")
    doc = fitz.open(pdf_path)
    for page_number, page, split_x in _iter_pages_with_split(doc, layout):
        page_lines = _extract_page_lines(page, split_x)
        marker = {
            "left": None,
            "right": None,
            "start_left": None,
            "start_right": None,
        }
        for column, lines in page_lines.items():
            for line in lines:
                normalized = _normalize_text(line.text)
                if layout == Layout.modern and marker[f"start_{column}"] is None:
                    if start_marker in normalized:
                        marker[f"start_{column}"] = line.y0
                if "comprasparceladas" in normalized:
                    marker[column] = line.y0
                    break
        yield page_number, page_lines, marker
        if marker["left"] is not None or marker["right"] is not None:
            break
    doc.close()


def _apply_marker(
    page_lines: dict[str, list[LineInfo]],
    marker: dict[str, float | None],
) -> tuple[list[LineInfo], list[LineInfo]]:
    left_lines = page_lines["left"]
    right_lines = page_lines["right"]
    if marker.get("start_left") is not None:
        left_lines = [line for line in left_lines if line.y0 > marker["start_left"]]
    if marker.get("start_right") is not None:
        right_lines = [line for line in right_lines if line.y0 > marker["start_right"]]
    if marker["left"] is not None:
        left_lines = [line for line in left_lines if line.y0 < marker["left"]]
        right_lines = []
    elif marker["right"] is not None:
        right_lines = [line for line in right_lines if line.y0 < marker["right"]]
    return left_lines, right_lines


def _extract_line_blocks(pdf_path: Path, layout: Layout = Layout.modern) -> list[str]:
    """Extract text blocks from line groups using the layout split."""
    blocks: list[str] = []
    for _, page_lines, marker in _iter_page_lines(pdf_path, layout):
        left_lines, right_lines = _apply_marker(page_lines, marker)
        if left_lines:
            blocks.append("\n".join(line.text for line in left_lines))
        if right_lines:
            blocks.append("\n".join(line.text for line in right_lines))
        if marker["left"] is not None or marker["right"] is not None:
            break
    return blocks


def _parse_statements_from_lines(
    lines: list[LineInfo],
    page_number: int,
    column: str,
    year: str,
    payment_date: str | None,
    statements: list[tuple[int, int, str, float, float, str]],
    index: int,
) -> int:
    i = 0
    while i < len(lines):
        date_line = lines[i]
        date_text = re.sub(r"\s+", "", date_line.text)
        if not re.match(r"^\d{1,2}/\d{1,2}$", date_text):
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not lines[j].text.strip():
            j += 1
        if j >= len(lines):
            break
        desc_line = lines[j]
        k = j + 1
        while k < len(lines) and not lines[k].text.strip():
            k += 1
        if k >= len(lines):
            break
        installment_line = None
        amount_line = lines[k]
        installment_text = re.sub(r"\s+", "", amount_line.text)
        if re.match(r"^\d{1,2}/\d{1,2}$", installment_text):
            installment_line = amount_line
            k += 1
            if k >= len(lines):
                break
            amount_line = lines[k]
        amount_text = _normalize_amount_text(amount_line.text)
        if amount_text is None:
            i += 1
            continue
        if installment_line is None:
            match = f"{date_text}\n{desc_line.text}\n{amount_text}"
        else:
            match = f"{date_text}\n{desc_line.text}\n{installment_text}\n{amount_text}"
        date_part, description, amount = match_to_csv(match, year).split(",", 2)
        payment_field = payment_date or ""
        row = f"{index},{date_part},{payment_field},{description},{amount}"
        statements.append((index, page_number, column, date_line.x0, date_line.y0, row))
        index += 1
        i = k + 1
    return index


def _normalize_amount_text(value: str) -> str | None:
    cleaned = re.sub(r"\s+", "", value)
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
        date_part, description, amount = match_to_csv(match, year).split(",", 2)
        category = statement["category"] or ""
        location = statement["location"] or ""
        output_rows.append(
            f"{index},{date_part},{payment_field},{description},{amount},{category},{location}"
        )
        index += 1
    return output_rows, index


def _parse_block_basic(
    block: str, year: str, payment_date: str | None, index: int
) -> tuple[list[str], int]:
    normalized_block = re.sub(
        r"(?m)^(\d{1,2})/(\d)\s+(\d)$",
        r"\1/\2\3",
        block,
    )
    lines = [line for line in normalized_block.splitlines() if line.strip()]
    output_rows: list[str] = []
    i = 0
    while i < len(lines):
        date_line = re.sub(r"\s+", "", lines[i])
        if not re.match(r"^\d{1,2}/\d{1,2}$", date_line):
            i += 1
            continue
        j = i + 1
        desc_lines: list[str] = []
        installment_line = None
        amount_line = None
        while j < len(lines):
            candidate = lines[j].strip()
            candidate_norm = re.sub(r"\s+", "", candidate)
            amount_text = _normalize_amount_text(candidate)
            if amount_text is not None:
                amount_line = amount_text
                break
            if re.match(r"^\d{1,2}/\d{1,2}$", candidate_norm):
                k = j + 1
                while k < len(lines) and not lines[k].strip():
                    k += 1
                if k < len(lines):
                    next_amount = _normalize_amount_text(lines[k])
                    if next_amount is not None:
                        installment_line = candidate_norm
                        amount_line = next_amount
                        j = k
                        break
            desc_lines.append(candidate)
            j += 1
        if amount_line and desc_lines:
            if installment_line:
                desc_lines.append(installment_line)
            match = f"{date_line}\n{' '.join(desc_lines)}\n{amount_line}"
            payment_field = payment_date or ""
            date_part, description, amount = match_to_csv(match, year).split(",", 2)
            output_rows.append(
                f"{index},{date_part},{payment_field},{description},{amount}"
            )
            index += 1
            i = j + 1
        else:
            i += 1
    return output_rows, index


def _iter_page_blocks(
    pdf_path: Path,
    layout: Layout = Layout.modern,
) -> Iterable[
    tuple[int, list[tuple[str, float, float, float, float, str]], dict[str, float | None]]
]:
    """Yield per-page blocks using the layout split."""
    start_marker = _normalize_text("lançamentos: compras e saques")
    doc = fitz.open(pdf_path)
    for page_number, page, split_x in _iter_pages_with_split(doc, layout):
        page_lines = _extract_page_lines(page, split_x)
        marker = {
            "left": None,
            "right": None,
            "start_left": None,
            "start_right": None,
        }
        for column, lines in page_lines.items():
            for line in lines:
                normalized = _normalize_text(line.text)
                if layout == Layout.modern and marker[f"start_{column}"] is None:
                    if start_marker in normalized:
                        marker[f"start_{column}"] = line.y0
                if "comprasparceladas" in normalized:
                    marker[column] = line.y0
                    break

        left_rect = fitz.Rect(page.rect.x0, page.rect.y0, split_x, page.rect.y1)
        right_rect = fitz.Rect(split_x, page.rect.y0, page.rect.x1, page.rect.y1)
        page_blocks: list[tuple[str, float, float, float, float, str]] = []

        for column, rect in (("left", left_rect), ("right", right_rect)):
            for block in page.get_text("blocks", clip=rect):
                if len(block) < 5:
                    continue
                text = block[4].strip()
                if not text:
                    continue
                x0, y0, x1, y1 = block[0], block[1], block[2], block[3]
                start_y = marker.get(f"start_{column}")
                end_y = marker.get(column)
                if start_y is not None and y0 <= start_y:
                    continue
                if end_y is not None and y0 >= end_y:
                    continue
                page_blocks.append((column, y0, x0, x1, y1, text))

        yield page_number, page_blocks, marker
        if marker["left"] is not None or marker["right"] is not None:
            break
    doc.close()


def _iter_pages_with_split(
    doc: fitz.Document, layout: Layout = Layout.modern
) -> Iterable[tuple[int, fitz.Page, float]]:
    """Yield pages with a split X coordinate based on the layout."""
    cm_to_pt = 28.35
    split_offsets_cm = {
        Layout.modern: (-1.0, 1.0),
        Layout.legacy: (0.0, 1.5),
    }
    first_offset_cm, other_offset_cm = split_offsets_cm.get(
        layout, split_offsets_cm[Layout.modern]
    )
    base_split_x: float | None = None
    for page_number, page in enumerate(doc, start=1):
        words = page.get_text("words")
        split_x = _compute_split_x(words, page.rect)
        if base_split_x is None:
            base_split_x = split_x
        offset_cm = first_offset_cm if page_number == 1 else other_offset_cm
        split_x_line = base_split_x + (offset_cm * cm_to_pt)
        yield page_number, page, split_x_line


def parse_brl_amount(value: str) -> float:
    """Parse a BRL-formatted amount (1.234,56) into a float."""
    cleaned = value.strip().replace(".", "").replace(",", ".")
    return float(cleaned)


def format_date_en_us(date_str: str) -> str:
    """Format DD/MM/YY to MM/DD/YY for CSV output."""
    if not date_str:
        return date_str
    try:
        parsed = datetime.strptime(date_str, "%d/%m/%y")
    except ValueError:
        return date_str
    return parsed.strftime("%m/%d/%y")


def find_total_in_text(text: str) -> float | None:
    """Find the statement total in raw or normalized PDF text."""
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
    """Normalize PDF text by removing accents, lowercasing, and stripping whitespace."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).lower()
    return re.sub(r"\s+", "", normalized)


def extract_total_from_pdf(pdf_path: Path) -> float | None:
    """Extract the statement total from a PDF."""
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return find_total_in_text(text)


def extract_raw_text(pdf_path: Path) -> str:
    """Return the raw PDF text, separated by blank lines between pages."""
    doc = fitz.open(pdf_path)
    text = "\n\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def extract_card_last4(pdf_path: Path) -> str | None:
    """Extract the last 4 digits of the card from the PDF text."""
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()

    masked_match = re.findall(r"X{4}\.(\d{4})", text, flags=re.IGNORECASE)
    if masked_match:
        return masked_match[-1]

    patterns = (
        r"(?:final|finais)\s*[:\-]?\s*(\d{4})",
        r"(?:Cart[aã]o|Cartao)[^\d]{0,20}(\d{4})",
    )
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            return matches[-1]

    normalized_text = normalize_pdf_text(text)
    matches = re.findall(
        r"(?:cartaofinal|cartaofinais|final|finais)(\d{4})", normalized_text
    )
    if matches:
        return matches[-1]
    matches = re.findall(r"cartao(\d{4})", normalized_text)
    if matches:
        return matches[-1]
    return None


def extract_emissao_year(pdf_path: Path) -> str | None:
    """Extract the two-digit year from the Emissao date in the PDF."""
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


def extract_invoice_payment_date(pdf_path: Path) -> str | None:
    """Extract the payment due date in DD/MM/YY format."""
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    match = re.search(
        r"Vencimento[^\d]{0,20}(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE
    )
    if not match:
        normalized_text = normalize_pdf_text(text)
        match = re.search(
            r"vencimento.*?(\d{2}/\d{2}/\d{4})", normalized_text
        )
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%d/%m/%Y").strftime("%d/%m/%y")
    except ValueError:
        return None


def month_number_for_date(date_str: str) -> tuple[str, str] | None:
    """Return (YYYY, MM) for a DD/MM/YY date string."""
    if not date_str:
        return None
    try:
        parsed = datetime.strptime(date_str, "%d/%m/%y")
    except ValueError:
        return None
    return parsed.strftime("%Y"), parsed.strftime("%m")


def blocks_to_statements(
    blocks: Iterable[str],
    year: str,
    payment_date: str | None,
    enhanced: bool = False,
) -> list[str]:
    """Process text blocks to extract raw statement entries.

    Each statement pattern: DD/MM, newline, description, newline, price value.
    """
    statements: list[str] = []
    index = 0
    for block in blocks:
        if enhanced:
            parsed, index = _parse_block_with_metadata(block, year, payment_date, index)
        else:
            parsed, index = _parse_block_basic(block, year, payment_date, index)
        statements.extend(parsed)
    return statements


def blocks_to_statements_with_layout(
    blocks: Iterable[BlockInfo],
    year: str,
    payment_date: str | None,
    enhanced: bool = False,
) -> list[tuple[int, int, str, float, float, str]]:
    """Process text blocks with layout metadata into statement entries."""
    statements: list[tuple[int, int, str, float, float, str]] = []
    index = 0
    for block in blocks:
        if enhanced:
            parsed, index = _parse_block_with_metadata(
                block.text, year, payment_date, index
            )
        else:
            parsed, index = _parse_block_basic(block.text, year, payment_date, index)
        for row in parsed:
            row_index = row.split(",", 1)[0]
            statements.append(
                (
                    int(row_index),
                    block.page,
                    block.column,
                    block.x0,
                    block.y0,
                    row,
                )
            )
    return statements


def extract_statement_rows_with_layout(
    pdf_path: Path,
    year: str,
    payment_date: str | None,
    layout: Layout = Layout.modern,
) -> list[tuple[int, int, str, float, float, str]]:
    """Extract statement rows with page/column metadata using the layout split."""
    statements: list[tuple[int, int, str, float, float, str]] = []
    index = 0
    for page_number, page_lines, marker in _iter_page_lines(pdf_path, layout):
        left_lines, right_lines = _apply_marker(page_lines, marker)
        index = _parse_statements_from_lines(
            left_lines, page_number, "left", year, payment_date, statements, index
        )
        index = _parse_statements_from_lines(
            right_lines, page_number, "right", year, payment_date, statements, index
        )
        if marker["left"] is not None or marker["right"] is not None:
            break
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
    """Flip the sign of the amount column for each CSV row."""
    new_data = []
    for row in csv_data:
        columns = row.split(",", 6)
        if len(columns) < 5:
            new_data.append(row)
            continue
        try:
            amount_value = float(columns[4].replace(",", "."))
            columns[4] = str(amount_value * -1)
        except ValueError:
            pass
        new_data.append(",".join(columns))
    return new_data


def localize_rows(rows: Iterable[str]) -> list[str]:
    """Format date columns for en-US CSV output."""
    localized: list[str] = []
    for row in rows:
        parts = row.split(",", 6)
        if len(parts) < 5:
            localized.append(row)
            continue
        row_id, transaction_date, payment_date, description, amount = parts[:5]
        extra = parts[5:] if len(parts) > 5 else []
        transaction_date = format_date_en_us(transaction_date)
        payment_date = format_date_en_us(payment_date)
        localized.append(
            ",".join([row_id, transaction_date, payment_date, description, amount] + extra)
        )
    return localized


def apply_id_schema(rows: Iterable[str]) -> list[str]:
    """Replace index with an id using YYYY-MMM-(index)."""
    months = EN_US_MONTH_ABBREVIATIONS
    output: list[str] = []
    for row in rows:
        parts = row.split(",", 6)
        if len(parts) < 5:
            output.append(row)
            continue
        index, transaction_date, payment_date, description, amount = parts[:5]
        extra = parts[5:] if len(parts) > 5 else []
        date_source = payment_date.strip() or transaction_date
        try:
            parsed = datetime.strptime(date_source, "%d/%m/%y")
            year = parsed.strftime("%Y")
            month = months[parsed.month - 1]
        except ValueError:
            year = "0000"
            month = "UNK"
        try:
            index_int = int(index)
        except ValueError:
            index_int = 0
        row_id = f"{year}-{month}-{index_int + 1}"
        output.append(
            ",".join([row_id, transaction_date, payment_date, description, amount] + extra)
        )
    return output


def check_total(csv_data: Iterable[str], expected_total: float) -> None:
    """Raise if the sum of amounts does not match the expected total."""
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
    rows: Iterable[str],
    output_path: Path | None,
    include_headers: bool = True,
    headers: list[str] | None = None,
) -> None:
    """Write CSV rows to stdout or a file."""
    headers = headers or CSV_HEADERS
    if output_path is None:
        if include_headers:
            print(",".join(headers))
        for line in rows:
            print(line)
        return

    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if include_headers:
            writer.writerow(headers)
        for row in rows:
            writer.writerow(row.split(","))


def load_existing_rows(output_path: Path, headers: list[str] | None = None) -> set[str]:
    """Load existing rows from a CSV file, excluding headers."""
    if not output_path.exists():
        return set()

    headers = headers or CSV_HEADERS
    with output_path.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        return {
            ",".join(row)
            for row in reader
            if row and row != headers
        }


def write_csv_lines_idempotent(
    rows: Iterable[str],
    output_path: Path,
    include_headers: bool = True,
    headers: list[str] | None = None,
) -> int:
    """Append rows to a CSV file, skipping rows already present."""
    headers = headers or CSV_HEADERS
    existing_rows = load_existing_rows(output_path, headers=headers)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    added = 0
    with output_path.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if include_headers and (not output_path.exists() or output_path.stat().st_size == 0):
            writer.writerow(headers)
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
    """Parse a single Itau PDF into CSV rows."""
    resolved_year = year or extract_emissao_year(pdf_path) or datetime.now().strftime("%y")
    payment_date = extract_invoice_payment_date(pdf_path)

    text_blocks = extract_blocks(pdf_path)
    statements = blocks_to_statements(text_blocks, resolved_year, payment_date)

    if total is not None:
        check_total(statements, total)

    return flip_sign_last_column(statements)

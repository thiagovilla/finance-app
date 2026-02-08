from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Literal, List

import fitz

from itau_pdf.utils import normalize_text


# Layout module goal: parse PDF, emit lines in flipped N order from start to stop marker


@dataclass(frozen=True)
class Page:
    index: int
    pdf: fitz.Page
    x_split: float


class Column(str, Enum):
    left = "left"
    right = "right"


@dataclass(frozen=True)
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


@dataclass(frozen=True)
class Line:
    """A line of text enriched with layout metadata."""
    text: str
    page: int
    column: Column
    # Geometry kept for debugging/annotation
    y0: float
    x0: float
    x1: float
    y1: float


def iter_lines(doc: fitz.Document) -> Iterator[Line]:
    """Yield lines in flipped N order from start to stop marker."""
    start_marker = False
    for page in _iter_pages(doc):
        for line in _iter_lines(page):
            if not start_marker and _has_marker(line, "start"):
                start_marker = True
                continue
            if not start_marker:
                continue
            if _has_marker(line, "stop"):
                return
            yield line


def _has_marker(line: Line, marker: Literal["start", "stop"]) -> bool:
    """Check if a line contains a marker."""
    normalized_text = normalize_text(line.text)
    if marker == "start":
        return "lancamentos:comprasesaques" in normalized_text
    elif marker == "stop":
        return "comprasparceladas" in normalized_text
    return False


# ---------- PAGES ----------

def _iter_pages(doc: fitz.Document) -> Iterator[Page]:
    """Yield pages with an x-split coordinate based on the layout."""
    for page in doc:
        x_split = _calc_x_plit(page)
        yield Page(page.number + 1, page, x_split)


def _calc_x_plit(page: fitz.Page) -> float:
    cm_to_pt = 28.35
    midpoint = _get_page_midpoint(page)
    offset = 0.0 if page.number == 0 else 1.7
    return midpoint + (offset * cm_to_pt)


def _get_page_midpoint(page: fitz.Page) -> float:
    x0, _, width, _ = page.rect
    return x0 + (width / 2)


# ---------- LINES ----------

def _iter_lines(page: Page) -> Iterator[Line] | None:
    """Yield lines in flipped N order (left then right column, top to bottom)."""
    if not (columns := _split_columns(page)):
        return None

    for col in [Column.left, Column.right]:
        yield from (line for line in columns.get(col, []))


def _split_columns(page: Page) -> dict[Column, list[Line]] | None:
    """Group words into left/right columns based on x_split."""
    if not (words := [Word(*w[:5]) for w in page.pdf.get_text("words")]):
        return None

    left_words = [w for w in words if w.x0 < page.x_split]
    right_words = [w for w in words if w.x0 >= page.x_split]

    return {
        Column.left: _group_words(left_words),
        Column.right: _group_words(right_words),
    }


def _group_words(words: List[Word], y_tol: float | None = None) -> List[Line]:
    """Decide which words belong on the same line and order them left-to-right."""
    if not words:
        return []

    y_tol = y_tol or _calc_y_tol(words)
    words_sorted = sorted(words, key=lambda w: (w.y0, w.x0))

    # 1st pass - decide which words belong on the same line
    raw_lines: List[dict] = []
    for word in words_sorted:
        if not raw_lines or abs(word.y0 - raw_lines[-1]["y0"]) > y_tol:
            raw_lines.append(
                {
                    "y0": word.y0,
                    "y1": word.y1,
                    "words": [word],
                }
            )
        else:
            raw_lines[-1]["y0"] = min(raw_lines[-1]["y0"], word.y0)
            raw_lines[-1]["y1"] = max(raw_lines[-1]["y1"], word.y1)
            raw_lines[-1]["words"].append(word)

    # 2nd pass - order words in line (turn into readable text)
    result: List[Line] = []
    for line_data in raw_lines:
        words_in_line = sorted(line_data["words"], key=lambda w: w.x0)
        text = " ".join(w.text for w in words_in_line).strip()
        if not text:
            continue

        result.append(Line(
            y0=line_data["y0"],
            y1=line_data["y1"],
            x0=words_in_line[0].x0,
            x1=words_in_line[-1].x1,
            text=text,
            column=Column.left,
            page=1
        ))
    return result


def _calc_y_tol(words: List[Word]) -> float:
    """Compute adaptive tolerance based on median height."""
    heights = sorted(word.y1 - word.y0 for word in words)
    median_height = heights[len(heights) // 2]
    # Tolerance is 30% of median height, at least 2.0 pts
    return max(2.0, median_height * 0.3)

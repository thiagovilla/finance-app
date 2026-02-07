from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Iterator, Literal

import fitz

from itau.utils import normalize_text
from itau.layout_lines import Word, Line, group_words_into_lines


class Layout(str, Enum):
    legacy = "legacy"
    modern = "modern"


@dataclass(frozen=True)
class Page:
    index: int
    object: fitz.Page
    x_split: float


class Column(str, Enum):
    left = "left"
    right = "right"


@dataclass(frozen=True)
class Block:
    page: int
    column: Column
    x0: float
    y0: float
    text: str


# TODO: I think this should be control flow?
def iter_pdf_blocks(pdf_path: str, layout: Layout = Layout.modern) -> Iterator[Block]:
    """Iterate through PDF pages, yielding text blocks in flipped N order from start to stop marker."""
    start_marker = False
    with fitz.open(pdf_path) as pdf:
        for page in _iter_pages(pdf, layout):
            for block in _iter_blocks(page):
                if not start_marker and _check_marker(block, "start"):
                    start_marker = True
                    continue
                if _check_marker(block, "stop"):
                    return
                yield block


def _iter_pages(doc: fitz.Document, layout: Layout) -> Iterator[Page]:
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
    for page_number, page in doc:
        words = page.get_text("words")
        x_split = _deprecated__calc_inter_word_x_split(words, page.rect)
        if base_split_x is None:
            base_split_x = x_split
        offset_cm = first_offset_cm if page_number == 1 else other_offset_cm
        split_x_line = base_split_x + (offset_cm * cm_to_pt)
        yield Page(page_number, page, split_x_line)


def _deprecated__calc_inter_word_x_split(words: list[tuple], page_rect: fitz.Rect) -> float:
    """Computes split point based on inter-word gaps"""
    x0_values = sorted(word[0] for word in words)
    if len(x0_values) < 2:
        return page_rect.x0 + (page_rect.width / 2)
    max_gap = 0.0
    x_split = page_rect.x0 + (page_rect.width / 2)
    prev = x0_values[0]
    for current in x0_values[1:]:
        gap = current - prev
        if gap > max_gap:
            max_gap = gap
            x_split = (prev + current) / 2
        prev = current
    min_x0 = x0_values[0]
    max_x0 = x0_values[-1]
    span = max_x0 - min_x0
    if span <= 0:
        return page_rect.x0 + (page_rect.width / 2)
    min_split = min_x0 + (span * 0.25)
    max_split = max_x0 - (span * 0.25)
    if max_gap >= 20.0 and min_split <= x_split <= max_split:
        return x_split
    return min_x0 + (span / 2)


def _iter_blocks(page: Page) -> Iterable[Block]:
    """Yield per-page blocks in flipped N order (Left column then Right column)."""
    columns = _split_into_columns(page)
    if not columns:
        return

    for col in [Column.left, Column.right]:
        for line in columns.get(col, []):
            yield Block(page.index, col, line.y0, line.x0, line.text)


def _split_into_columns(page: Page) -> dict[Column, list[Line]] | None:
    """Group words into lines based on whether they fall left or right of the x_split."""
    raw_words = page.object.get_text("words")
    if not raw_words:
        return None

    words = [Word(x0=w[0], y0=w[1], x1=w[2], y1=w[3], text=w[4]) for w in raw_words]

    left_words = [w for w in words if w.x0 < page.x_split]
    right_words = [w for w in words if w.x0 >= page.x_split]

    return {
        Column.left: group_words_into_lines(left_words),
        Column.right: group_words_into_lines(right_words),
    }


def _check_marker(block: Block, marker: Literal["start", "stop"]) -> bool:
    """Check if a block contains a marker."""
    normalized_text = normalize_text(block.text)
    if marker == "start":
        return "lancamentos:comprasesaques" in normalized_text
    elif marker == "stop":
        return "comprasparceladas" in normalized_text
    return False

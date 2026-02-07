from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


@dataclass(frozen=True)
class Line:
    y0: float
    x0: float
    x1: float
    y1: float
    text: str


def group_words_into_lines(words: List[Word], y_tol: float | None = None) -> List[Line]:
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
            text=text
        ))
    return result


def _calc_y_tol(words: List[Word]) -> float:
    """Compute adaptive tolerance based on median height."""
    heights = sorted(word.y1 - word.y0 for word in words)
    median_height = heights[len(heights) // 2]
    # Tolerance is 30% of median height, at least 2.0 pts
    return max(2.0, median_height * 0.3)

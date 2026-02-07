from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from itau_pdf.layout import Block


@dataclass(frozen=True)
class Statement:
    date: datetime
    amount: float
    description: str


def _parse_block(block: Block) -> Iterator[Statement]:
    """A block may contain more than one statement"""
    return None


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

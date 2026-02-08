import re
from dataclasses import dataclass
from typing import Iterator

from itau_pdf.layout import Line
from itau_pdf.utils import parse_brl_amount


@dataclass(frozen=True)
class Statement:
    date: str # Kept as DD/MM string
    amount: float # Kept as BRL
    description: str
    category: str
    location: str


def parse_statements(lines: Iterator[Line]) -> Iterator[Statement]:
    """
    Parses lines into statements. Lines may not be consecutive.
    Line 1: DD/MM <description> <amount>
    Line 2: <category> . <location> (or just <category>)
    """
    current_stmt: dict | None = None
    for line in lines:
        text = line.text.strip()

        # 1. Match Line 1: Date, Description, Amount
        # Handles: "23/01 AMAZON*MARKETPLACE 02/08 -170,00" or "15/02 IFOOD 42,50"
        # Regex: date (DD/MM), then anything (description), then BRL amount
        if first_line_match := re.match(r"^(\d{2}/\d{2})\s+(.+?)\s+((?:-\s)?[\d.]+,\d{2})$", text, re.IGNORECASE):
            # Yield pending statement that never got a Line 2
            if current_stmt:
                yield Statement(**current_stmt)

            current_stmt = {
                "date": first_line_match.group(1),
                "description": first_line_match.group(2).strip(),
                "amount": first_line_match.group(3),
                "category": "",
                "location": "",
            }
            continue

        # 2. Match Line 2: Category and Location
        # Handles: "DIVERSOS . CURITIBA" or "SAUDE"
        if current_stmt and text:
            # Check for "Category . Location" pattern
            if "." in text:
                parts = text.split(".", 1)
                current_stmt["category"] = parts[0].strip()
                current_stmt["location"] = parts[1].strip()
            else:
                # One word only: assume it's category
                current_stmt["category"] = text

            yield Statement(**current_stmt)
            current_stmt = None

    # Yield any final pending statement
    if current_stmt:
        yield Statement(**current_stmt)

# --------------- STATEMENT EXTRACTION ---------------

# def _blocks_to_statements(blocks: Iterable[str], year: str, payment_date: str | None) -> list[str]:
#     statements: list[str] = []
#     index = 1
#     for block in blocks:
#         parsed, index = _parse_block_basic(block, year, payment_date, index)
#         statements.extend(parsed)
#     return statements
#
#
# def _parse_block_basic(block: str, year: str, payment_date: str | None, index: int) -> tuple[list[str], int]:
#     normalized_block = re.sub(r"(?m)^(\d{1,2})/(\d)\s+(\d)$", r"\1/\2\3", block)
#     lines = [line for line in normalized_block.splitlines() if line.strip()]
#     output_rows: list[str] = []
#     i = 0
#     while i < len(lines):
#         date_line = re.sub(r"\s+", "", lines[i])
#         if not re.match(r"^\d{1,2}/\d{1,2}$", date_line):
#             i += 1
#             continue
#         j, desc_lines, inst_line, amt_line = i + 1, [], None, None
#         while j < len(lines):
#             line = lines[j].strip()
#             amt = _normalize_amount_text(line)
#             if amt:
#                 amt_line = amt
#                 break
#             if re.match(r"^\d{1,2}/\d{1,2}$", re.sub(r"\s+", "", line)) and j + 1 < len(lines):
#                 next_amt = _normalize_amount_text(lines[j + 1])
#                 if next_amt:
#                     inst_line, amt_line = re.sub(r"\s+", "", line), next_amt
#                     j += 1
#                     break
#             desc_lines.append(line)
#             j += 1
#         if amt_line and desc_lines:
#             match = f"{date_line}\n{' '.join(desc_lines)}\n{inst_line or ''}\n{amt_line}".replace("\n\n", "\n")
#             d_part, desc, amt = _match_to_csv(match, year).split(",", 2)
#             row_id = _generate_itau_id(payment_date or d_part, index)
#             output_rows.append(f"{row_id},{d_part},{payment_date or ''},{desc},{amt},itau_cc")
#             index, i = index + 1, j + 1
#         else:
#             i += 1
#     return output_rows, index

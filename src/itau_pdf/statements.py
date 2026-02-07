import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from itau_pdf.layout import Line
from itau_pdf.utils import parse_brl_amount


@dataclass(frozen=True)
class Statement:
    date: datetime
    amount: float
    description: str
    category: str
    location: str


# assume only valid lines
def _parse_lines(lines: Iterator[Line]) -> Iterator[Statement]:
    """Match "23/01 AMAZON MARKETPLACE 170,00" or "DIVERSOS .CURITIBA\""""
    index = 1
    statement = {
        "date": datetime.now(),
        "description": "",
        "amount": 0.0,
        "category": "",
        "location": "",
    }
    for line in lines:
        text = line.text.strip()
        print(f"DEBUG: Will match on line: {repr(text)}")

        if matches := re.match(r"^(\d{2}/\d{2})\s*(.+?)\s*(-?[\d.]+,\d{2})$", text):
            print(f"DEBUG: Matched line: {repr(matches)}")
            statement["date"] = datetime.strptime(matches.group(1), "%d/%m")
            statement["description"] = matches.group(2).strip()
            statement["amount"] = parse_brl_amount(matches.group(3))
            yield Statement(**statement)

        # 2. Match Category/Location format: "DIVERSOS .CURITIBA"
        # If there's only one, there's no way to know which is which; assume category
        # if matches := re.match(r"^(\w+)\s*\.\s*(\w*)$", line.text):
        #     print(f"DEBUG: Matched line: {repr(matches)}")
        #     statement["category"] = matches.group(1)
        #     statement["location"] = matches.group(2)
        #     temp_statement = statement.copy()
        #     statement.clear()
        #     yield Statement(**temp_statement)


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

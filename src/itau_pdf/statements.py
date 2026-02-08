import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterator

from itau_pdf.layout import Line
from itau_pdf.utils import parse_brl_amount


@dataclass(frozen=True)
class Statement:
    id: str = ""
    date: "str | date" = ""  # Kept as DD/MM string
    description: str = ""
    amount: float = 0.0
    category: str = ""
    location: str = ""


def parse_lines(lines: Iterator[Line], payment_date: date) -> Iterator[Statement]:
    """
    Parses lines into statements. Lines may not be consecutive.
    Line 1: DD/MM <description> <amount>
    Line 2: <category> . <location> (or just <category>)
    """
    index = 1
    current_stmt: dict | None = None
    for line in lines:
        text = line.text.strip()
        if not text:
            continue

        # 1. Match Line 1: Date, Description, Amount
        # Handles: "23/01 AMAZON*MARKETPLACE 02/08 -170,00" or "15/02 IFOOD 42,50"
        # Regex: date (DD/MM), then anything (description), then BRL amount
        if first_line_match := re.match(r"^(\d{2}/\d{2})\s+(.+?)\s+((?:-\s?)?[\d.]+,\d{2})$", text, re.IGNORECASE):
            if current_stmt:
                yield Statement(**current_stmt)
            current_stmt = {
                "id": f"{payment_date.strftime("%Y-%b")}-{index:03d}",
                "date": _parse_date(first_line_match.group(1), payment_date),
                "description": first_line_match.group(2).strip(),
                "amount": -parse_brl_amount(first_line_match.group(3)),
                "category": "",
                "location": "",
            }
            index += 1
            continue

        # 2. Match Line 2: Category and Location
        # Handles: "DIVERSOS . CURITIBA" or "SAUDE"
        if current_stmt:
            if "." in text:
                parts = text.split(".", 1)
                current_stmt["category"] = parts[0].strip()
                current_stmt["location"] = parts[1].strip()
            else:
                current_stmt["category"] = text
            yield Statement(**current_stmt)
            current_stmt = None

    if current_stmt:
        yield Statement(**current_stmt)


def _parse_date(dm_date_str: str, payment_date: date) -> date:
    parsed_date = datetime.strptime(dm_date_str, "%d/%m").date()
    year = payment_date.year
    if payment_date.month == 1 and parsed_date.month == 12:
        year -= 1
    return parsed_date.replace(year)

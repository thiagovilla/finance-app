import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Iterator

from itau_pdf.layout import Line
from itau_pdf.utils import parse_brl_amount, parse_dm_date


@dataclass(frozen=True)
class Statement:
    id: str = ""
    date: "str | date" = ""  # Kept as DD/MM string
    description: str = ""
    amount: float = 0.0
    category: str = ""
    location: str = ""


def parse_lines(lines: Iterator[Line]) -> Iterator[Statement]:
    """
    Parses lines into statements. Lines may not be consecutive.
    Line 1: DD/MM <description> <amount>
    Line 2: <category> . <location> (or just <category>)
    """
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
                "date": first_line_match.group(1),
                "description": first_line_match.group(2).strip(),
                "amount": parse_brl_amount(first_line_match.group(3)),
                "category": "",
                "location": "",
            }
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


def flip_sign(statements: Iterator[Statement]) -> Iterator[Statement]:
    """Flips the sign of the amount for each statement."""
    for statement in statements:
        yield replace(statement, amount=-statement.amount)


def add_year(statements: Iterator[Statement], issue_date: date) -> Iterator[Statement]:
    """Adds the given year to the date of each statement."""
    for statement in statements:
        if not isinstance(statement.date, str):
            continue
        parsed_date = parse_dm_date(statement.date)
        year = issue_date.year - 1 if issue_date.month == 1 and parsed_date.month == 12 else issue_date.year
        yield replace(statement, date=parsed_date.replace(year=year))


def add_id(statements: Iterator[Statement], payment_date: date) -> Iterator[Statement]:
    """Adds an ID to each statement in the format YYYY-MMM-<index>."""
    for index, statement in enumerate(statements, start=1):
        yield replace(statement, id=f"{payment_date.year}-{payment_date.strftime('%b')}-{index}")

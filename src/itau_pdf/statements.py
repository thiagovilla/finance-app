import re
from dataclasses import dataclass
from typing import Iterator

from itau_pdf.layout import Line


@dataclass(frozen=True)
class Statement:
    date: str  # Kept as DD/MM string
    amount: float  # Kept as BRL
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

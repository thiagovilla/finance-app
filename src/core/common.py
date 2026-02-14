import csv
import json
import re
import unicodedata
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Statement:
    id: str
    transaction_date: date
    description: str
    amount: float
    payment_date: date | None = None
    category: str = ""
    location: str = ""
    tags: str = ""
    account: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        # Convert dates to ISO format (YYYY-MM-DD)
        data["transaction_date"] = self.transaction_date.isoformat()
        if self.payment_date:
            data["payment_date"] = self.payment_date.isoformat()
        else:
            data["payment_date"] = ""
        # Ensure amount is formatted to 2 decimal places
        data["amount"] = f"{self.amount:.2f}"
        return data


COMMON_FIELDNAMES = [
    "id",
    "transaction_date",
    "payment_date",
    "description",
    "amount",
    "category",
    "location",
    "tags",
    "account",
]


def write_statements_csv(statements: Iterable[Statement], output_path: Path, force: bool = False) -> int:
    """
    Writes statements idempotently to a CSV file using the common format.
    Use force=True to overwrite.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = output_path.exists()
    existing_ids = set()
    if file_exists and not force:
        with output_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_ids = {row["id"] for row in reader if "id" in row}

    mode = "w" if force or not file_exists else "a"
    count = 0
    with output_path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COMMON_FIELDNAMES)
        if mode == "w":
            writer.writeheader()
        for stmt in statements:
            if stmt.id not in existing_ids:
                writer.writerow(stmt.to_dict())
                existing_ids.add(stmt.id)
                count += 1
    return count


def parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start: end + 1])
        raise

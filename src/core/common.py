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

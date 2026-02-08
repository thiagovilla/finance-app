from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

CSV_HEADERS = ["id", "transaction_date", "payment_date", "description", "amount", "acc"]


# this is definitely control flow, not lib
def check_total(csv_data: Iterable[str], expected_total: float) -> None:
    try:
        total_sum = sum(float(row.split(",")[4]) for row in csv_data)
        if round(total_sum, 2) != round(expected_total, 2):
            raise ValueError(f"Total mismatch: expected {expected_total:.2f}, got {total_sum:.2f}")
    except (IndexError, ValueError) as exc:
        raise ValueError("Error validating totals.") from exc


# --------------- I/O & IDEMPOTENCY ---------------

def write_csv_lines_idempotent(rows: Iterable[str], output_path: Path, include_headers: bool = True,
                               headers: list[str] | None = None) -> int:
    headers = headers or CSV_HEADERS
    existing_ids = set()
    if output_path.exists():
        with output_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                existing_ids = {r["id"] for r in reader if "id" in r}

    added = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if output_path.exists() else "w"
    with output_path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if mode == "w" and include_headers:
            writer.writerow(headers)
        for row in rows:
            parts = row.split(",")
            if parts[0] not in existing_ids:
                writer.writerow(parts)
                existing_ids.add(parts[0])
                added += 1
    return added

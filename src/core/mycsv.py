import csv
from pathlib import Path
from typing import Iterable

from core.common import Statement

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

    csv_content, count = statements_to_csv(
        statements=statements,
        existing_ids=existing_ids,
        include_header=(force or not file_exists)
    )

    mode = "w" if force or not file_exists else "a"
    with output_path.open(mode, newline="", encoding="utf-8") as f:
        f.write(csv_content)

    return count


def statements_to_csv(
        statements: Iterable[Statement],
        existing_ids: set[str] = None,
        include_header: bool = True,
) -> tuple[str, int]:
    """
    Generates CSV content in memory for the given statements.
    
    Args:
        statements: Iterable of Statement objects to write
        existing_ids: Set of IDs that already exist (to skip duplicates)
        include_header: Whether to include the CSV header row
    
    Returns:
        Tuple of (csv_content as string, count of new rows written)
    """
    import io
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=COMMON_FIELDNAMES)

    if include_header:
        writer.writeheader()

    count = 0
    for stmt in statements:
        if existing_ids is None or stmt.id not in existing_ids:
            writer.writerow(stmt.to_dict())
            existing_ids.add(stmt.id)
            count += 1

    return output.getvalue(), count

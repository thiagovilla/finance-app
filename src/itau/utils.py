import re
import unicodedata
from datetime import datetime


def normalize_text(text: str) -> str:
    """Normalize text by removing accents, lowercasing, and stripping whitespace."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).lower()
    return re.sub(r"\s+", "", normalized)


def parse_brl_amount(value: str) -> float:
    """Parse a BRL-formatted amount (1.234,56) into a float."""
    cleaned = value.strip().replace(".", "").replace(",", ".")
    return float(cleaned)


def dmy_to_mdy(date_str: str) -> str:
    """Format DD/MM/YY to MM/DD/YY for CSV output."""
    if not date_str:
        return date_str
    try:
        parsed = datetime.strptime(date_str, "%d/%m/%y")
    except ValueError:
        return date_str
    return parsed.strftime("%m/%d/%y")


# --------------- UTILS ---------------

# def _generate_itau_id(date_str: str, index: int) -> str:
#     """Helper to generate the YYYY-MMM-index ID."""
#     try:
#         # date_str is either DD/MM/YY (from match_to_csv) or payment_date
#         parsed = datetime.strptime(date_str, "%d/%m/%y")
#         year = parsed.strftime("%Y")
#         month = MONTH_ABBREVIATIONS[parsed.month - 1]
#     except ValueError:
#         year = "0000"
#         month = "UNK"
#     return f"{year}-{month}-{index}"

import re
import unicodedata


def normalize_text(text: str) -> str:
    """Normalize text by removing accents, lowercasing, and stripping whitespace."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).lower()
    return re.sub(r"\s+", "", normalized)


def parse_brl_amount(value: str) -> float:
    """Parse a BRL-formatted amount (1.234,56) into a float."""
    cleaned = value.replace(" ", "").replace(".", "").replace(",", ".")
    return float(cleaned)

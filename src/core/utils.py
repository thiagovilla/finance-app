import re
import unicodedata


def normalize_description(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = "".join(char for char in cleaned if not unicodedata.combining(char))
    cleaned = re.sub(r"\b(?:parc|parcela|parcelado|parcelamento)\b", " ", cleaned)
    cleaned = re.sub(r"\b\w+\d{1,2}\s*/\s*\d{1,2}\b", " ", cleaned)  # ?
    cleaned = re.sub(r"\b\w+\d{1,2}\s+\d{1,2}\b", " ", cleaned)  # ?
    cleaned = re.sub(r"\b\d{1,2}\s*/\s*\d{1,2}\b", " ", cleaned)  # ?
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    previous = None
    while cleaned != previous:
        previous = cleaned
        cleaned = re.sub(r"\b([a-z])\s+(?=[a-z]\b)", r"\1", cleaned)
    return cleaned.strip()

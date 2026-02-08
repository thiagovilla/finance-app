import re
from datetime import datetime

from itau_pdf.utils import parse_brl_amount


def extract_last4(pdf_text: str) -> str | None:
    """Extract the last 4 digits of the card from the PDF text (XXXX.1234)."""
    if masked_match := re.findall(r"x{4}\.(\d{4})", pdf_text, flags=re.IGNORECASE):
        return masked_match[-1]
    return None


def extract_total(text: str) -> float | None:
    """Find the statement total in raw or normalized PDF text."""
    total_patterns = (
        r"total\s+desta\s+fatura\s*\n\s*(?:r\$)?\s*([\d\.]+,\d{2})",
        r"o\s+total\s+da\s+sua\s+fatura\s+é:\s*\n?\s*r\$\s*([\d\.]+,\d{2})",
        r"total\s+da\s+fatura(?!\s+anterior)\s*\n?\s*(?:r\$)?\s*([\d\.]+,\d{2})",
    )
    for pattern in total_patterns:
        if match := re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            return parse_brl_amount(match.group(1))
    return None


def extract_payment_date(text: str) -> datetime | None:
    """Extract the invoice payment date after "vencimento"."""
    if not (match := re.search(r"vencimento\D*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)):
        return None
    try:
        return datetime.strptime(match.group(1), "%d/%m/%Y")
    except ValueError:
        return None


def extract_issue_date(text: str) -> datetime | None:
    """Extract the invoice issue date after "emissão"."""
    if not (match := re.search(r"emiss[aã]o:?\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)):
        return None
    try:
        return datetime.strptime(match.group(1), "%d/%m/%Y")
    except ValueError:
        return None

import re
from datetime import datetime

from itau.utils import normalize_text, parse_brl_amount


def extract_last4(pdf_text: str) -> str | None:
    """Extract the last 4 digits of the card from the PDF text (XXXX.1234)."""
    masked_match = re.findall(r"X{4}\.(\d{4})", pdf_text, flags=re.IGNORECASE)
    if masked_match:
        return masked_match[-1]

    # TODO: Needed?
    # patterns = (
    #     r"(?:final|finais)\s*[:\-]?\s*(\d{4})",
    #     r"(?:Cart[aã]o|Cartao)[^\d]{0,20}(\d{4})",
    # )
    # for pattern in patterns:
    #     matches = re.findall(pattern, text, flags=re.IGNORECASE)
    #     if matches:
    #         return matches[-1]
    #
    # normalized_text = _normalize_text(text)
    # matches = re.findall(
    #     r"(?:cartaofinal|cartaofinais|final|finais)(\d{4})", normalized_text
    # )
    # if matches:
    #     return matches[-1]
    # matches = re.findall(r"cartao(\d{4})", normalized_text)
    # if matches:
    #     return matches[-1]
    return None


def extract_total(text: str) -> float | None:
    """Find the statement total in raw or normalized PDF text."""
    total_patterns = (
        r"Total\s+desta\s+fatura\s*\n\s*(?:R\$)?\s*([\d\.]+,\d{2})",
        r"O\s+total\s+da\s+sua\s+fatura\s+é:\s*\n?\s*R\$\s*([\d\.]+,\d{2})",
        r"Total\s+da\s+fatura(?!\s+anterior)\s*\n?\s*(?:R\$)?\s*([\d\.]+,\d{2})",
    )
    for pattern in total_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return parse_brl_amount(match.group(1))

    # TODO: Needed?
    # normalized_text = _normalize_text(text)
    # labels = ("ototaldasuafaturae", "totaldestafatura")
    # for label in labels:
    #     match = re.search(
    #         rf"{label}.{{0,200}}?(?:r\$)?([\d.]+,\d{{2}})",
    #         normalized_text,
    #         flags=re.DOTALL,
    #     )
    #     if match:
    #         return _parse_brl_amount(match.group(1))
    return None


def extract_payment_date(text: str) -> datetime | None:
    """Extract the invoice payment date after "vencimento"."""
    match = re.search(
        r"Vencimento\D{0,20}(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE  # TODO: What is \D{0,20} for?
    )
    # TODO: Shouldn't we match against normalized text first?
    if not match:
        normalized_text = normalize_text(text)
        match = re.search(r"vencimento.*?(\d{2}/\d{2}/\d{4})", normalized_text)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%d/%m/%Y")
    except ValueError:
        return None


def extract_issue_date(text: str) -> datetime | None:
    """Extract the date from the 'Emissão' field in the PDF."""
    if match := re.search(r"Emiss[aã]o:?\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE):
        try:
            return datetime.strptime(match.group(1), "%d/%m/%Y")
        except ValueError:
            pass
    return None

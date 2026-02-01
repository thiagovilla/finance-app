from __future__ import annotations

from pathlib import Path
import hashlib
import re
import unicodedata

import pandas as pd

BASE_HEADERS = ["id", "transaction_date", "payment_date", "description", "amount"]


def convert_date_format(input_csv: Path, output_csv: Path | None = None) -> Path:
    """Convert the first column to DD/MM/YYYY and flip the third column sign."""
    output_path = output_csv or input_csv

    df = pd.read_csv(input_csv)
    df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0]).dt.strftime("%d/%m/%Y")

    if len(df.columns) > 2:
        df.iloc[:, 2] *= -1

    df.to_csv(output_path, index=False)
    return output_path


def parse_nubank_csv(
    input_csv: Path,
    output_csv: Path | None = None,
    *,
    template: str,
) -> Path:
    df = pd.read_csv(input_csv)
    column_map = {_normalize_header(name): name for name in df.columns}

    date_col = _find_column(column_map, _DATE_HEADERS)
    desc_col = _find_column(column_map, _DESC_HEADERS)
    amount_col = _find_column(column_map, _AMOUNT_HEADERS)
    if date_col is None or desc_col is None or amount_col is None:
        missing = []
        if date_col is None:
            missing.append("date")
        if desc_col is None:
            missing.append("description")
        if amount_col is None:
            missing.append("amount")
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    payment_col = _find_column(column_map, _PAYMENT_HEADERS)
    category_col = _find_column(column_map, _CATEGORY_HEADERS)
    location_col = _find_column(column_map, _LOCATION_HEADERS)
    tags_col = _find_column(column_map, _TAG_HEADERS)
    id_col = _find_column(column_map, _ID_HEADERS)

    dates = _parse_dates(df[date_col])
    if dates.isna().any():
        raise ValueError("Found invalid transaction dates in the CSV.")
    transaction_date = dates.dt.strftime("%Y-%m-%d")

    payment_date = None
    if payment_col is not None:
        parsed = _parse_dates(df[payment_col])
        if parsed.isna().any():
            raise ValueError("Found invalid payment dates in the CSV.")
        payment_date = parsed.dt.strftime("%Y-%m-%d")

    amounts = pd.to_numeric(df[amount_col], errors="coerce")
    if amounts.isna().any():
        raise ValueError("Found invalid amounts in the CSV.")
    if template == "nubank_cc":
        amounts = amounts * -1

    descriptions = df[desc_col].astype(str).str.strip()

    categories = df[category_col].astype(str).str.strip() if category_col else None
    locations = df[location_col].astype(str).str.strip() if location_col else None
    tags = df[tags_col].astype(str).str.strip() if tags_col else None

    if id_col:
        row_ids = df[id_col].astype(str).str.strip()
    else:
        row_ids = [
            _stable_row_id(
                template,
                txn_date,
                payment_date.iloc[idx] if payment_date is not None else None,
                descriptions.iloc[idx],
                amounts.iloc[idx],
            )
            for idx, txn_date in enumerate(transaction_date)
        ]

    data: dict[str, pd.Series | list[str]] = {
        "id": row_ids,
        "transaction_date": transaction_date,
        "payment_date": payment_date if payment_date is not None else "",
        "description": descriptions,
        "amount": amounts.map(lambda value: f"{value:.2f}"),
    }

    headers = BASE_HEADERS.copy()
    if categories is not None:
        data["category"] = categories
        headers.append("category")
    if tags is not None:
        data["tags"] = tags
        headers.append("tags")
    if locations is not None:
        data["location"] = locations
        headers.append("location")

    output_path = output_csv or input_csv.with_name(f"{input_csv.stem}_parsed.csv")
    pd.DataFrame(data, columns=headers).to_csv(output_path, index=False)
    return output_path


def _normalize_header(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = "".join(char for char in cleaned if not unicodedata.combining(char))
    cleaned = re.sub(r"[^a-z0-9]+", "", cleaned)
    return cleaned


def _find_column(
    column_map: dict[str, str],
    candidates: set[str],
) -> str | None:
    for key in candidates:
        if key in column_map:
            return column_map[key]
    return None


def _parse_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=True)


def _stable_row_id(
    template: str,
    txn_date: str,
    payment_date: str | None,
    description: str,
    amount: float,
) -> str:
    parts = [template, txn_date, payment_date or "", description, f"{amount:.2f}"]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"sha1:{digest}"


_DATE_HEADERS = {
    "date",
    "data",
    "transactiondate",
    "datatransacao",
    "datadatransacao",
}
_PAYMENT_HEADERS = {"paymentdate", "postdate", "datapagamento", "datapostagem"}
_DESC_HEADERS = {"description", "descricao", "title", "details", "historico", "history"}
_AMOUNT_HEADERS = {"amount", "valor", "value", "quantia"}
_CATEGORY_HEADERS = {"category", "categoria"}
_LOCATION_HEADERS = {"location", "local", "merchant", "estabelecimento"}
_TAG_HEADERS = {"tags"}
_ID_HEADERS = {"id", "identifier", "identificador", "transactionid", "uuid"}

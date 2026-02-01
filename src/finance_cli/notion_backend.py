from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path

from finance_cli.db import (
    ImportResult,
    _hash_import_id,
    _normalize_row,
    _parse_amount_cents,
    _parse_date,
)


_SOURCE_TO_ACCOUNT = {
    "itau_cc": "Itaú 7180",
    "nubank_cc": "Nubank CC",
    "nubank_chk": "Nubank 2240",
}
_ACCOUNT_TO_SOURCE = {
    "itau 7180": "itau_cc",
    "nubank cc": "nubank_cc",
    "nubank 2240": "nubank_chk",
}


@dataclass(frozen=True)
class NotionConfig:
    token: str
    database_id: str


def load_notion_config() -> NotionConfig:
    token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")
    if not token or not database_id:
        raise RuntimeError("Missing NOTION_TOKEN or NOTION_DATABASE_ID.")
    if re.fullmatch(r"[0-9a-fA-F]{32}", database_id):
        database_id = (
            f"{database_id[0:8]}-"
            f"{database_id[8:12]}-"
            f"{database_id[12:16]}-"
            f"{database_id[16:20]}-"
            f"{database_id[20:32]}"
        )
    return NotionConfig(token=token, database_id=database_id)


def derive_account_from_filename(path: Path) -> str | None:
    stem = path.stem
    parts = stem.split("_")
    if len(parts) >= 3:
        account_raw = "_".join(parts[:-2])
    else:
        account_raw = stem
    account_raw = account_raw.replace("_", " ").strip()
    return normalize_account_name(account_raw)


def normalize_account_name(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    tokens = cleaned.split()
    if tokens and tokens[0].lower() == "itau":
        tokens[0] = "Itaú"
    if tokens and tokens[0].lower() == "nubank":
        tokens[0] = "Nubank"
    if tokens and tokens[-1].lower() == "cc":
        tokens[-1] = "CC"
    return " ".join(tokens)


def account_from_source(source: str | None) -> str | None:
    if not source:
        return None
    return _SOURCE_TO_ACCOUNT.get(source)


def source_from_account(account: str | None) -> str | None:
    if not account:
        return None
    key = normalize_account_name(account)
    if not key:
        return None
    return _ACCOUNT_TO_SOURCE.get(key.lower())


def import_csv_to_notion(
    csv_path: Path,
    *,
    source: str | None,
    account: str | None,
    currency: str = "BRL",
) -> ImportResult:
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    config = load_notion_config()
    notion = _create_notion_client(config.token)

    inserted = 0
    skipped = 0

    with csv_path.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)

    if not rows:
        return ImportResult(inserted=0, skipped=0)

    account_name = normalize_account_name(account or "")
    if not account_name:
        account_name = account_from_source(source) or derive_account_from_filename(csv_path)
    if not account_name:
        raise ValueError("Could not determine account name for Notion import.")

    for row in rows:
        normalized = _normalize_row(row)
        txn_date = _parse_date(normalized.transaction_date)
        if txn_date is None:
            skipped += 1
            continue
        post_date = _parse_date(normalized.payment_date) if normalized.payment_date else None
        amount_cents = _parse_amount_cents(normalized.amount)
        raw_import_id = normalized.raw_id or _hash_import_id(
            source=source or account_name,
            txn_date=txn_date,
            post_date=post_date,
            description=normalized.description,
            amount_cents=amount_cents,
        )

        if _notion_has_external_id(notion, config.database_id, raw_import_id):
            skipped += 1
            continue

        properties = _build_notion_properties(
            normalized_description=normalized.description,
            external_id=raw_import_id,
            account_name=account_name,
            amount_cents=amount_cents,
            txn_date=txn_date,
            post_date=post_date,
            category=normalized.category,
            tags=normalized.tags,
            reconciled=True,
        )

        notion.pages.create(
            parent={"database_id": config.database_id},
            properties=properties,
        )
        inserted += 1

    return ImportResult(inserted=inserted, skipped=skipped)


def fetch_notion_pages(
    *,
    since: str | None,
) -> list[dict]:
    config = load_notion_config()
    notion = _create_notion_client(config.token)

    pages: list[dict] = []
    start_cursor = None
    while True:
        payload: dict = {"database_id": config.database_id, "page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        if since:
            payload["filter"] = {
                "timestamp": "last_edited_time",
                "last_edited_time": {"on_or_after": since},
            }
        result = _query_database(notion, **payload)
        pages.extend(result.get("results", []))
        if not result.get("has_more"):
            break
        start_cursor = result.get("next_cursor")
    return pages


def update_notion_category(
    *,
    external_id: str,
    category: str,
) -> bool:
    if not external_id or not category:
        return False
    config = load_notion_config()
    notion = _create_notion_client(config.token)
    page_id = _find_page_id_by_external_id(notion, config.database_id, external_id)
    if not page_id:
        return False
    notion.pages.update(
        page_id=page_id,
        properties={
            "Category": {"select": {"name": category}},
        },
    )
    return True


def _create_notion_client(token: str):
    try:
        from notion_client import Client
    except ImportError as exc:
        raise RuntimeError("notion-client is required for Notion support.") from exc
    return Client(auth=token)


def _query_database(notion, **payload) -> dict:
    databases = getattr(notion, "databases", None)
    if databases and hasattr(databases, "query"):
        return databases.query(**payload)
    if databases and hasattr(databases, "query_database"):
        return databases.query_database(**payload)
    if hasattr(notion, "request"):
        database_id = payload.pop("database_id")
        return notion.request("POST", f"/databases/{database_id}/query", json=payload)
    if hasattr(notion, "client") and hasattr(notion.client, "request"):
        database_id = payload.pop("database_id")
        return notion.client.request(
            "POST", f"/databases/{database_id}/query", json=payload
        )
    raise RuntimeError("Notion client does not support database queries.")


def _notion_has_external_id(notion, database_id: str, external_id: str) -> bool:
    if not external_id:
        return False
    result = _query_database(
        notion,
        database_id=database_id,
        filter={
            "property": "External ID",
            "rich_text": {"equals": external_id},
        },
        page_size=1,
    )
    return bool(result.get("results"))


def _find_page_id_by_external_id(notion, database_id: str, external_id: str) -> str | None:
    result = _query_database(
        notion,
        database_id=database_id,
        filter={
            "property": "External ID",
            "rich_text": {"equals": external_id},
        },
        page_size=1,
    )
    results = result.get("results", [])
    if not results:
        return None
    return results[0].get("id")


def _build_notion_properties(
    *,
    normalized_description: str,
    external_id: str,
    account_name: str,
    amount_cents: int,
    txn_date: str,
    post_date: str | None,
    category: str | None,
    tags: str | None,
    reconciled: bool,
) -> dict:
    title_value = normalized_description.strip() or external_id or "Statement"
    properties = {
        "ID_old": {"title": [{"text": {"content": title_value}}]},
        "External ID": {"rich_text": [{"text": {"content": external_id}}]},
        "Description": {"rich_text": [{"text": {"content": normalized_description}}]},
        "Account": {"select": {"name": account_name}},
        "Amount": {"number": amount_cents / 100},
        "Transaction Date": {"date": {"start": txn_date}},
        "Reconciled": {"checkbox": reconciled},
    }
    if post_date:
        properties["Payment Date"] = {"date": {"start": post_date}}
    if category:
        properties["Category"] = {"select": {"name": category}}
    if tags:
        tag_values = [tag.strip() for tag in tags.split(",") if tag.strip()]
        if tag_values:
            properties["Tags"] = {"multi_select": [{"name": tag} for tag in tag_values]}
    return properties


def parse_notion_statement(page: dict) -> dict | None:
    props = page.get("properties") or {}
    external_id = _extract_rich_text(props.get("External ID"))
    description = _extract_rich_text(props.get("Description"))
    title = _extract_title(props.get("ID_old"))
    if not description:
        description = title
    if not external_id:
        return None

    amount = _extract_number(props.get("Amount"))
    txn_date = _extract_date(props.get("Transaction Date"))
    if not txn_date or amount is None:
        return None
    post_date = _extract_date(props.get("Payment Date"))
    category = _extract_select(props.get("Category"))
    tags = _extract_multi_select(props.get("Tags"))
    account = _extract_select(props.get("Account"))

    return {
        "external_id": external_id,
        "description": description,
        "amount": amount,
        "transaction_date": txn_date,
        "payment_date": post_date,
        "category": category,
        "tags": tags,
        "account": account,
    }


def _extract_rich_text(prop: dict | None) -> str:
    if not prop or prop.get("type") != "rich_text":
        return ""
    parts = [item.get("plain_text", "") for item in prop.get("rich_text", [])]
    return "".join(parts).strip()


def _extract_title(prop: dict | None) -> str:
    if not prop or prop.get("type") != "title":
        return ""
    parts = [item.get("plain_text", "") for item in prop.get("title", [])]
    return "".join(parts).strip()


def _extract_number(prop: dict | None) -> float | None:
    if not prop or prop.get("type") != "number":
        return None
    return prop.get("number")


def _extract_date(prop: dict | None) -> str | None:
    if not prop or prop.get("type") != "date":
        return None
    date_value = prop.get("date") or {}
    return date_value.get("start")


def _extract_select(prop: dict | None) -> str | None:
    if not prop or prop.get("type") != "select":
        return None
    select = prop.get("select") or {}
    return select.get("name")


def _extract_multi_select(prop: dict | None) -> str | None:
    if not prop or prop.get("type") != "multi_select":
        return None
    items = prop.get("multi_select") or []
    names = [item.get("name") for item in items if item.get("name")]
    if not names:
        return None
    return ", ".join(names)

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from notion_client import Client


@dataclass(frozen=True)
class NotionConfig:
    token: str
    database_id: str


@lru_cache(maxsize=1)
def _get_notion_config() -> NotionConfig:
    """Reads and caches config from environment variables."""
    token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")
    if not token or not database_id:
        raise RuntimeError("Missing NOTION_TOKEN or NOTION_DATABASE_ID.")
    return NotionConfig(token=token, database_id=database_id)


@lru_cache(maxsize=1)
def _get_notion_client() -> Client:
    """Returns a singleton-like Notion client instance."""
    config = _get_notion_config()
    return Client(auth=config.token)


def get_notion_page(page_id: str) -> dict | None:
    """Fetch a single page by its Notion page_id."""
    notion = _get_notion_client()
    try:
        return notion.pages.retrieve(page_id=page_id)
    except Exception:
        return None


def query_notion_pages(filter_params: dict | None = None) -> list[dict]:
    """
    Efficiently fetch pages from Notion database using a generic filter.
    Handles pagination automatically.
    """
    config = _get_notion_config()
    notion = _get_notion_client()

    pages: list[dict] = []
    start_cursor = None

    while True:
        payload: dict = {"database_id": config.database_id, "page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        if filter_params:
            payload["filter"] = filter_params

        result = notion.databases.query(**payload)
        pages.extend(result.get("results", []))

        if not result.get("has_more"):
            break
        start_cursor = result.get("next_cursor")

    return pages


def upsert_notion_page(page_id: str | None, properties: dict) -> str | None:
    """
    Creates a new page if page_id is None, otherwise updates existing page.
    Returns the page_id (new or existing).
    """
    if page_id is None:
        return _create_notion_page(properties)
    else:
        _update_notion_page(page_id, properties)
        return page_id


def batch_upsert_pages(entries: list[tuple[str | None, dict]]) -> dict[str, int]:
    """
    Upserts multiple pages to Notion.
    
    Args:
        entries: List of tuples (page_id, properties). 
                 page_id=None means create, otherwise update.
    
    Returns:
        Dict with keys 'created', 'updated', 'failed' counting operations.
    """
    created = 0
    updated = 0
    failed = 0

    for page_id, props in entries:
        try:
            result_id = upsert_notion_page(page_id, props)
            if result_id:
                if page_id is None:
                    created += 1
                else:
                    updated += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    return {"created": created, "updated": updated, "failed": failed}


def _create_notion_page(properties: dict) -> str | None:
    """Creates a page with the provided properties and returns the new page_id."""
    config = _get_notion_config()
    notion = _get_notion_client()
    try:
        response = notion.pages.create(
            parent={"database_id": config.database_id},
            properties=properties,
        )
        return response.get("id")
    except Exception:
        return None


def _update_notion_page(page_id: str, properties: dict) -> bool:
    """Updates an existing Notion page by its id with provided properties."""
    notion = _get_notion_client()
    try:
        notion.pages.update(page_id=page_id, properties=properties)
        return True
    except Exception:
        return False


def deprecated_batch_create_pages(entries_properties: list[dict]) -> int:
    """
    Writes multiple pages to Notion.
    Expects a list of pre-formatted Notion property dictionaries.

    DEPRECATED: Use batch_upsert_pages instead.
    """
    return batch_upsert_pages([(None, props) for props in entries_properties])["created"]

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from finance_cli.notion import (
    NotionConfig,
    _create_notion_page,
    _get_notion_client,
    _get_notion_config,
    _update_notion_page,
    batch_upsert_pages,
    deprecated_batch_create_pages,
    get_notion_page,
    query_notion_pages,
    upsert_notion_page,
)


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Fixture to mock environment variables for Notion configuration."""
    monkeypatch.setenv("NOTION_TOKEN", "test_token_12345")
    monkeypatch.setenv("NOTION_DATABASE_ID", "test_db_id_67890")
    # Clear LRU cache to ensure fresh config in each test
    _get_notion_config.cache_clear()
    _get_notion_client.cache_clear()


@pytest.fixture
def mock_notion_client():
    """Fixture to provide a mocked Notion client."""
    with patch("finance_cli.notion.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        yield mock_client


def test_get_notion_config_valid(mock_env_vars):
    """Test that _get_notion_config returns valid config from environment variables."""
    config = _get_notion_config()
    assert isinstance(config, NotionConfig)
    assert config.token == "test_token_12345"
    assert config.database_id == "test_db_id_67890"


def test_get_notion_config_missing_vars():
    """Test that _get_notion_config raises RuntimeError when env vars are missing."""
    _get_notion_config.cache_clear()
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="Missing NOTION_TOKEN or NOTION_DATABASE_ID"):
            _get_notion_config()


def test_get_notion_client(mock_env_vars, mock_notion_client):
    """Test that _get_notion_client returns a Client instance."""
    client = _get_notion_client()
    assert client is not None


def test_get_notion_page_success(mock_env_vars, mock_notion_client):
    """Test get_notion_page returns page data on success."""
    mock_notion_client.pages.retrieve.return_value = {"id": "page123", "properties": {}}

    result = get_notion_page("page123")

    assert result == {"id": "page123", "properties": {}}
    mock_notion_client.pages.retrieve.assert_called_once_with(page_id="page123")


def test_get_notion_page_exception(mock_env_vars, mock_notion_client):
    """Test get_notion_page returns None on exception."""
    mock_notion_client.pages.retrieve.side_effect = Exception("API Error")

    result = get_notion_page("page123")

    assert result is None


def test_query_notion_pages_no_pagination(mock_env_vars, mock_notion_client):
    """Test query_notion_pages without pagination."""
    mock_notion_client.databases.query.return_value = {
        "results": [{"id": "page1"}, {"id": "page2"}],
        "has_more": False,
    }

    result = query_notion_pages()

    assert len(result) == 2
    assert result[0]["id"] == "page1"
    assert result[1]["id"] == "page2"


def test_query_notion_pages_with_pagination(mock_env_vars, mock_notion_client):
    """Test query_notion_pages handles pagination correctly."""
    mock_notion_client.databases.query.side_effect = [
        {
            "results": [{"id": "page1"}, {"id": "page2"}],
            "has_more": True,
            "next_cursor": "cursor123",
        },
        {
            "results": [{"id": "page3"}],
            "has_more": False,
        },
    ]

    filter_params = {"property": "Status", "select": {"equals": "Active"}}
    result = query_notion_pages(filter_params)

    assert len(result) == 3
    assert result[0]["id"] == "page1"
    assert result[2]["id"] == "page3"
    assert mock_notion_client.databases.query.call_count == 2


def test_upsert_notion_page_create(mock_env_vars, mock_notion_client):
    """Test upsert_notion_page creates a new page when page_id is None."""
    mock_notion_client.pages.create.return_value = {"id": "new_page_id"}
    properties = {"Name": {"title": [{"text": {"content": "Test"}}]}}

    result = upsert_notion_page(None, properties)

    assert result == "new_page_id"
    mock_notion_client.pages.create.assert_called_once()


def test_upsert_notion_page_update(mock_env_vars, mock_notion_client):
    """Test upsert_notion_page updates an existing page when page_id is provided."""
    properties = {"Name": {"title": [{"text": {"content": "Updated"}}]}}

    result = upsert_notion_page("existing_page_id", properties)

    assert result == "existing_page_id"
    mock_notion_client.pages.update.assert_called_once_with(
        page_id="existing_page_id", properties=properties
    )


def test_batch_upsert_pages_mixed(mock_env_vars, mock_notion_client):
    """Test batch_upsert_pages with mixed create and update operations."""
    mock_notion_client.pages.create.return_value = {"id": "new_id"}

    entries = [
        (None, {"Name": {"title": [{"text": {"content": "New"}}]}}),
        ("existing_id", {"Name": {"title": [{"text": {"content": "Update"}}]}}),
    ]

    result = batch_upsert_pages(entries)

    assert result["created"] == 1
    assert result["updated"] == 1
    assert result["failed"] == 0


def test_batch_upsert_pages_with_failures(mock_env_vars, mock_notion_client):
    """Test batch_upsert_pages handles failures correctly."""
    mock_notion_client.pages.create.side_effect = Exception("API Error")

    entries = [
        (None, {"Name": {"title": [{"text": {"content": "Fail"}}]}}),
    ]

    result = batch_upsert_pages(entries)

    assert result["created"] == 0
    assert result["updated"] == 0
    assert result["failed"] == 1


def test_create_notion_page_success(mock_env_vars, mock_notion_client):
    """Test _create_notion_page returns new page_id on success."""
    mock_notion_client.pages.create.return_value = {"id": "new_page_id"}
    properties = {"Name": {"title": [{"text": {"content": "Test"}}]}}

    result = _create_notion_page(properties)

    assert result == "new_page_id"


def test_create_notion_page_exception(mock_env_vars, mock_notion_client):
    """Test _create_notion_page returns None on exception."""
    mock_notion_client.pages.create.side_effect = Exception("API Error")
    properties = {"Name": {"title": [{"text": {"content": "Test"}}]}}

    result = _create_notion_page(properties)

    assert result is None


def test_update_notion_page_success(mock_env_vars, mock_notion_client):
    """Test _update_notion_page returns True on success."""
    properties = {"Name": {"title": [{"text": {"content": "Updated"}}]}}

    result = _update_notion_page("page123", properties)

    assert result is True
    mock_notion_client.pages.update.assert_called_once()


def test_update_notion_page_exception(mock_env_vars, mock_notion_client):
    """Test _update_notion_page returns False on exception."""
    mock_notion_client.pages.update.side_effect = Exception("API Error")
    properties = {"Name": {"title": [{"text": {"content": "Updated"}}]}}

    result = _update_notion_page("page123", properties)

    assert result is False


def test_deprecated_batch_create_pages(mock_env_vars, mock_notion_client):
    """Test deprecated_batch_create_pages creates multiple pages."""
    mock_notion_client.pages.create.return_value = {"id": "new_id"}

    entries = [
        {"Name": {"title": [{"text": {"content": "Page1"}}]}},
        {"Name": {"title": [{"text": {"content": "Page2"}}]}},
    ]

    result = deprecated_batch_create_pages(entries)

    assert result == 2


def test_config_and_client_caching(mock_env_vars):
    """Test that _get_notion_config and _get_notion_client use LRU cache."""
    config1 = _get_notion_config()
    config2 = _get_notion_config()
    assert config1 is config2  # Same instance due to caching

    client1 = _get_notion_client()
    client2 = _get_notion_client()
    assert client1 is client2  # Same instance due to caching

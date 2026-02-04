import json
from pathlib import Path
from datetime import datetime
import typer
from finance_cli.notion import (
    _get_notion_client,
    get_notion_page,
)

notion_app = typer.Typer(help="Direct Notion integration helpers.")


def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


@notion_app.command("search")
def notion_search(
        query: str = typer.Argument(..., help="Query to search for in Notion pages.")
) -> None:
    """Search for a page containing the query."""
    notion = _get_notion_client()
    results = notion.search(query=query).get("results", [])
    if not results:
        typer.echo("No results found.")
        return

    for page in results:
        page_id = page.get("id")
        # Try to find a title in properties
        title = "Untitled"
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title_parts = prop.get("title", [])
                if title_parts:
                    title = title_parts[0].get("plain_text", title)
                break

        typer.echo(f"{page_id} | {title}")


@notion_app.command("get")
def notion_get(
        page_id: str = typer.Argument(..., help="The Notion page ID.")
) -> None:
    """Return page <id> as JSON."""
    page = get_notion_page(page_id)
    if not page:
        typer.echo(f"Page {page_id} not found.", err=True)
        raise typer.Exit(code=1)

    typer.echo(json.dumps(page, indent=2, default=json_serializer))


@notion_app.command("put")
def notion_put(
        page_id: str = typer.Argument(..., help="The Notion page ID."),
        file_path: Path = typer.Argument(..., help="JSON file containing page properties to update."),
) -> None:
    """Read file.json and upsert page <id>."""
    if not file_path.exists():
        typer.echo(f"File not found: {file_path}", err=True)
        raise typer.Exit(code=1)

    try:
        data = json.loads(file_path.read_text())
    except Exception as e:
        typer.echo(f"Failed to parse JSON: {e}", err=True)
        raise typer.Exit(code=1)

    notion = _get_notion_client()

    # Notion API: update properties or create if we want "upsert" logic.
    # Here we assume updating an existing page's properties.
    try:
        updated_page = notion.pages.update(page_id=page_id, properties=data.get("properties", data))
        typer.echo(f"Successfully updated page {page_id}")
        typer.echo(json.dumps(updated_page, indent=2, default=json_serializer))
    except Exception as e:
        typer.echo(f"Error updating Notion: {e}", err=True)
        raise typer.Exit(code=1)

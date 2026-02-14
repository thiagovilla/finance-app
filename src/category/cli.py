import typer

import category.manage as manage

app = typer.Typer(help="Personal finance CLI.")


@app.command("add")
def add_category(
        name: str = typer.Argument(..., help="Category name."),
        description: str = typer.Argument("", help="Optional description."),
) -> None:
    """Add a new finance category."""
    cat = manage.add_category(name, description)
    typer.echo(f"Added category: {cat.name} (id: {cat.id})")


@app.command("remove")
def remove_category(
        category_id: int = typer.Argument(..., help="ID of the category to remove.")
) -> None:
    """Remove a finance category by ID."""
    remove_category(category_id)
    typer.echo(f"Removed category {category_id}")


@app.command("list")
def list_categories() -> None:
    """List all finance categories."""
    categories = manage.list_categories()
    if not categories:
        typer.echo("No categories found.")
        return
    for cat in categories:
        desc = f" - {cat.description}" if cat.description else ""
        typer.echo(f"[{cat.id}] {cat.name}{desc}")


@app.command("update")
def update_category(
        category_id: int = typer.Argument(..., help="ID of the category to update."),
        name: str = typer.Argument(..., help="New category name."),
        description: str = typer.Argument("", help="New description."),
) -> None:
    """Update a finance category's name or description."""
    category = manage.get_category(category_id)
    if not category:
        typer.echo(f"Category {category_id} not found.")
        return
    manage.update_category(category_id, name, description or category.description)
    typer.echo(f"Updated category {category_id}")


@app.command("normalize")
def normalize_categories(force: bool = typer.Option(False, "--force", "-f", help="Force normalization even if no changes are needed.")) -> None:
    """Normalize category names."""
    app.normalize_categories(force)
    typer.echo("Category names and descriptions normalized.")
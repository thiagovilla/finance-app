from category.models import Category
from core.db import connect_db


def get_category(id: int) -> Category | None:
    with connect_db() as conn:
        row = conn.execute("SELECT id, name, description FROM categories WHERE id = ?", (id,)).fetchone()
        return Category(id=row[0], name=row[1], description=row[2]) if row else None


def list_categories() -> list[Category]:
    with connect_db() as conn:
        rows = conn.execute("SELECT id, name, description FROM categories").fetchall()
        return [Category(id=row[0], name=row[1], description=row[2]) for row in rows]


def add_category(name, description="") -> Category:
    with connect_db() as conn:
        conn.execute(
            "INSERT INTO categories (name, description) VALUES (?, ?)",
            (name, description),
        )
        return Category(id=conn.lastrowid, name=name, description=description)


def remove_category(id: int) -> None:
    with connect_db() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (id,))


def update_category(category: Category) -> None:
    if category.id is None:
        return

    with connect_db() as conn:
        conn.execute(
            "UPDATE categories SET name = ?, description = ? WHERE id = ?",
            (category.name, category.description, category.id),
        )

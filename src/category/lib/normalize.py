from category.repo import (
    get_all_statements,
    get_all_unnormalized_statements,
    batch_update_normalized_descriptions,
)
from core.utils import normalize_description


def normalize_all_descriptions(force=False) -> int:
    """Normalize all descriptions in the database using a batch update."""
    statements = get_all_statements() if force else get_all_unnormalized_statements()
    updates = [
        (normalize_description(stmt.description), stmt.id)
        for stmt in statements
    ]
    return batch_update_normalized_descriptions(updates)

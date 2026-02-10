from dataclasses import dataclass


@dataclass(frozen=True):
class Category:
    """Dataclass defining a category."""
    name: str
    description: str

# this is control flow
def categorize(description: str, threshold = 0.85, ai_hint = ""):
    # Normalize text
    # 1. Exact match (O(1) lookup): SELECT category FROM rules WHERE normalized_description = ? AND category IS NOT NULL
    # 2. Fuzzy search (SQLite FTS5): SELECT * FROM transaction_fts WHERE transaction_fts MATCH ?
    # 3. AI hint: if FTS5 score below threshold
    return Category

def find_exact_match(normalized_description: str) -> str | None:
    # run query, requires db
    return None

def fuzzy_search(description: str) -> str | None:
    return None

def ask_ai(description: str, hint = "") -> str | None:
    return None
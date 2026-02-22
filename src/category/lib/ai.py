from typing import List

from category.models import Suggestion
from core.ai import ask_ai
from core.common import parse_json
from core.models import Statement
from core.mycsv import statements_to_csv


def ask_ai_one(statement: Statement, hint="", top=5) -> List[Suggestion]:
    """Use AI to suggest a category for the description."""
    prompt = "Todo: get from settings"
    system = (
        f"{prompt.strip()}\n\n"
        f"Categories: "  # todo 
        "Return only JSON with key: category, confidence (0-1). Language: pt-br."
    )
    user = (
        f"Description: {statement.normalized_description}\n"
        f"Hint: {hint}"
        f"Return up to {top} category suggestions."
    )
    return _get_suggestions(system, user)


def ask_ai_many(statements: list[Statement]) -> List[Suggestion]:
    """Use AI to suggest categories for a list of statements."""
    system = (
        f"Categorize the following statements in order.\n\n"
        f"Categories: <list of categories>\n\n"
        f"Return JSON with keys: category, confidence (0-1). Language: pt-br."
    )
    user = f"Statements CSV:\n\n{statements_to_csv(statements)[0]}"
    return _get_suggestions(system, user)


def _get_suggestions(system, user):
    data = parse_json(ask_ai(system, user))
    return [Suggestion(**s) for s in data.get("suggestions") or []]


def _statements_to_csv(statements: list[Statement]) -> str:
    return "\n".join([f"{s.id},{s.text},{s.category}" for s in statements])

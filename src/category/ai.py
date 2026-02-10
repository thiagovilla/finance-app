from typing import List

from category.main import Suggestion
from core.ai import ask_ai
from core.common import parse_json


def ask_single(canonical_description: str, hint: str, language: str = "pt-br", top: int = 5) -> List[Suggestion]:
    """
    Use AI to suggest a category for the description.
    """
    prompt = "Todo: get from settings"
    system = (
        f"{prompt.strip()}\n\n"
        f"Categories: " # todo 
        "Return only JSON with key: category, confidence."
    )
    user = (
        f"Description: {canonical_description}\n"
        f"Hint: {hint}"
        f"Language: {language}\n"
        f"Return up to {top} category suggestions."
    )
    input = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    data = parse_json(ask_ai(input))
    return [Suggestion(**s) for s in data.get("suggestions") or []]

# TODO
def ask_batch(canonical_description: list[str]) -> List[List[Suggestion]]:
    return []
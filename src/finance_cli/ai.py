from __future__ import annotations

import json
from dataclasses import dataclass


class AiError(RuntimeError):
    pass


@dataclass(frozen=True)
class AiCategorization:
    category: str
    tags: list[str]
    confidence: float | None


@dataclass(frozen=True)
class AiCategorySuggestions:
    categories: list[str]


def categorize_description(
    description: str,
    *,
    model: str,
    api_key: str,
    prompt: str,
    language: str = "pt-br",
) -> AiCategorization:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AiError("OpenAI dependency missing. Install with `pip install openai`.") from exc

    client = OpenAI(api_key=api_key)
    system = (
        f"{prompt.strip()}\n\n"
        "Return only JSON with keys: category, tags, confidence. "
        "tags must be an array of short strings. "
        "confidence must be a number between 0 and 1."
    )
    user = (
        f"Description: {description}\n"
        f"Language: {language}\n"
        "If unsure, choose a generic category and low confidence."
    )
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = response.output_text
    data = _parse_json(content)
    category = str(data.get("category") or "").strip()
    if not category:
        raise AiError("Model returned empty category.")
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    tags = [str(tag).strip() for tag in tags if str(tag).strip()]
    confidence = data.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None
    return AiCategorization(
        category=category,
        tags=tags,
        confidence=confidence,
    )


def suggest_categories(
    description: str,
    *,
    model: str,
    api_key: str,
    prompt: str,
    language: str = "pt-br",
    top: int = 5,
) -> AiCategorySuggestions:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AiError("OpenAI dependency missing. Install with `pip install openai`.") from exc

    client = OpenAI(api_key=api_key)
    system = (
        f"{prompt.strip()}\n\n"
        "Return only JSON with key: categories. "
        "categories must be an array of short strings."
    )
    user = (
        f"Description: {description}\n"
        f"Language: {language}\n"
        f"Return up to {top} category suggestions."
    )
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = response.output_text
    data = _parse_json(content)
    categories = data.get("categories") or []
    if isinstance(categories, str):
        categories = [cat.strip() for cat in categories.split(",") if cat.strip()]
    categories = [str(cat).strip() for cat in categories if str(cat).strip()]
    return AiCategorySuggestions(categories=categories[: max(1, top)])


def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    name: str
    id: int | None = None
    description: str = ""


@dataclass(frozen=True)
class Suggestion:
    category: Category
    confidence: float

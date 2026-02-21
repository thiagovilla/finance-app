from dataclasses import dataclass
from enum import Enum
from core.models import Statement

class MatchMethod(Enum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    AI = "ai"
    FAILED = "failed"

@dataclass(frozen=True)
class Category:
    name: str

@dataclass(frozen=True)
class Suggestion:
    category: Category
    confidence: float

@dataclass(frozen=True)
class CategorizedStatement:
    statement: Statement
    match_method: MatchMethod
    confidence: float = 1.0

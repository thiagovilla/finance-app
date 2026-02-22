from dataclasses import replace

from category.lib.search import find_exact_match, search_suggestions
from category.models import CategorizedStatement, MatchMethod, Suggestion
from core.models import Statement


def find_exact_or_search(statement: Statement, top: int, threshold: float):
    """
    Attempts exact match; returns fuzzy match if above threshold.
    """
    if exact_match := find_exact_match(statement):
        return CategorizedStatement(
            statement=replace(statement, category=exact_match.name),
            match_method=MatchMethod.EXACT
        )

    if suggestions := search_suggestions(statement, top=top):
        if best_suggestion := get_first_above_threshold(suggestions, threshold):
            return CategorizedStatement(
                statement=replace(statement, category=best_suggestion.category.name),
                match_method=MatchMethod.FUZZY,
                confidence=best_suggestion.confidence
            )

    return None


def get_first_above_threshold(suggestions: list[Suggestion], threshold: float) -> Suggestion | None:
    for suggestion in suggestions:
        if suggestion.confidence >= threshold:
            return suggestion
    return None

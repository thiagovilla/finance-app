from collections import Counter
from dataclasses import replace

from category.lib.ai import ask_ai_many, ask_ai_one
from category.lib.utils import find_exact_or_search, get_first_above_threshold
from category.models import CategorizedStatement, MatchMethod
from core.models import Statement


def categorize_one(statement: Statement, top=5, threshold=0.85) -> CategorizedStatement:
    """
    Categorizes statement via exact match, search, or AI.
    """
    if match := find_exact_or_search(statement, top, threshold):
        return match

    if ai_suggestions := ask_ai_one(statement, top=top):
        if best_ai_suggestion := get_first_above_threshold(ai_suggestions, threshold=threshold):
            return CategorizedStatement(
                statement=replace(statement, category=best_ai_suggestion.category.name),
                match_method=MatchMethod.AI,
                confidence=best_ai_suggestion.confidence
            )

    return CategorizedStatement(statement=statement, match_method=MatchMethod.FAILED)


def categorize_many(statements: list[Statement], top=5, threshold=0.85) -> list[CategorizedStatement]:
    """
    Batch-categorizes statements and returns them wrapped with match metadata.
    """
    results: list[CategorizedStatement] = []
    ask_ai_list: list[Statement] = []

    for stmt in statements:
        if match := find_exact_or_search(stmt, top=top, threshold=threshold):
            results.append(match)
            continue

        ask_ai_list.append(stmt)

    # Use AI to categorize statements that failed exact/search
    if ask_ai_list:
        ai_suggestions = ask_ai_many(ask_ai_list)
        for stmt, suggestion in zip(ask_ai_list, ai_suggestions):
            good = suggestion.confidence >= threshold
            results.append(CategorizedStatement(
                statement=stmt if not good else replace(stmt, category=suggestion.category.name),
                match_method=MatchMethod.FAILED if not good else MatchMethod.AI,
                confidence=1 if not good else suggestion.confidence
            ))

    return results


def get_categorization_stats(results: list[CategorizedStatement]) -> dict:
    """
    Aggregates statistics from a list of categorized statements.
    """
    counts = Counter(r.match_method for r in results)

    return {
        "exact_matches": counts[MatchMethod.EXACT],
        "fuzzy_matches": counts[MatchMethod.FUZZY],
        "ask_ai": counts[MatchMethod.AI],
        "failed": counts[MatchMethod.FAILED],
        "updated": len([r for r in results if r.match_method != MatchMethod.FAILED]),
        "total": len(results)
    }

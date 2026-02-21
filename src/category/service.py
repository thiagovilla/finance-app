from collections import Counter
from dataclasses import replace

from category.lib.search import find_exact_match, search_best, fuzzy_search
from models import CategorizedStatement, MatchMethod, Category, Suggestion
from lib.ai import batch_ask_ai
from core.models import Statement


def categorize_single(statement: Statement, threshold=0.85) -> CategorizedStatement:
    if (exact_match := find_exact_match(statement)):
        return CategorizedStatement(
            statement=replace(statement, category=exact_match.name),
            match_method=MatchMethod.EXACT
        )

    if search_result := search_best(statement, threshold):
        return CategorizedStatement(
            statement=replace(statement, category=search_result.category.name),
            match_method=MatchMethod.FUZZY,
            confidence=search_result.confidence
        )

    # TODO ask AI top N return 1st that meets threshold

    return CategorizedStatement(statement=statement, match_method=MatchMethod.FAILED)


def categorize_batch(statements: list[Statement], threshold=0.85) -> list[CategorizedStatement]:
    """
    Batch-categorizes statements and returns them wrapped with match metadata.
    """
    results: list[CategorizedStatement] = []
    ask_ai_list: list[Statement] = []

    for stmt in statements:
        # 1. Tier: Exact Match
        if exact_match := find_exact_match(stmt):
            results.append(CategorizedStatement(
                statement=replace(stmt, category=exact_match.name),
                match_method=MatchMethod.EXACT
            ))
            continue

        # 2. Tier: Fuzzy Match (FTS)
        if suggestions := fuzzy_search(stmt, 1):
            if suggestions[0].confidence >= threshold:
                results.append(CategorizedStatement(
                    statement=replace(stmt, category=suggestions[0].category.name),
                    match_method=MatchMethod.FUZZY,
                    confidence=suggestions[0].confidence
                ))
                continue

        # 3. Tier: Prepare for AI
        ask_ai_list.append(stmt)

    if ask_ai_list:
        ai_suggestions = batch_ask_ai(ask_ai_list)
        for stmt, suggestion in zip(ask_ai_list, ai_suggestions):
            good = suggestion.confidence >= threshold
            results.append(CategorizedStatement(
                statement=stmt if not good else replace(stmt, category=suggestion.category.name),
                match_method=MatchMethod.FAILED if not good else MatchMethod.AI,
                confidence=suggestion.confidence
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

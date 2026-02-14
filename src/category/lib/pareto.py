from dataclasses import dataclass

from category.repo import get_uncategorized_counts


@dataclass(frozen=True)
class ParetoDataPoint:
    normalized_description: str
    count: int
    cumulative_pct: float
    is_top_80: bool


def get_pareto_data() -> list[ParetoDataPoint]:
    """
    Calculate Pareto data for uncategorized statements.
    Returns:
        List of dicts with description, count, cumulative percentage, and whether it's within the top 80% of volume.
    """
    counts = get_uncategorized_counts()
    if not counts:
        return []

    total_transactions = sum(count for _, count in counts)
    cumulative_count = 0
    pareto_data = []

    for normalized_desc, count in counts:
        prev_pct = (cumulative_count / total_transactions) * 100
        cumulative_count += count
        cumulative_pct = (cumulative_count / total_transactions) * 100

        pareto_data.append({
            "description": normalized_desc,
            "count": count,
            "cumulative_pct": cumulative_pct,
            "is_top_80": prev_pct < 80
        })

    return pareto_data

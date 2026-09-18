"""
Pre-flight estimate so the user sees roughly what a bulk run will cost
*before* it fires any API calls.

Figures are India Route Matrix Essentials pricing at the time this project
was built: 70,000 free elements/month, then $1.50 per 1,000 elements.
Google's pricing can change - check console.cloud.google.com/billing for
current rates before relying on this for real budgeting.
"""
from __future__ import annotations

from dataclasses import dataclass

FREE_ELEMENTS_PER_MONTH = 70_000
PRICE_PER_1000_ELEMENTS_USD = 1.50


@dataclass
class CostEstimate:
    unique_pairs: int
    likely_within_free_tier: bool
    estimated_cost_usd: float


def estimate(unique_pairs: int, already_used_this_month: int = 0) -> CostEstimate:
    """
    `unique_pairs` is the number of distinct (source, destination) pairs
    that actually need an API call - i.e. after dedup and cache lookups,
    not the raw row count.
    """
    remaining_free = max(FREE_ELEMENTS_PER_MONTH - already_used_this_month, 0)
    billable = max(unique_pairs - remaining_free, 0)
    cost = (billable / 1000) * PRICE_PER_1000_ELEMENTS_USD
    return CostEstimate(
        unique_pairs=unique_pairs,
        likely_within_free_tier=billable == 0,
        estimated_cost_usd=round(cost, 2),
    )

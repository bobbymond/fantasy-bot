"""Official-style FPL scoring constants for **2025/26** (single season, hardcoded).

Re-check against the live “How points are scored” page when FPL changes copy:
https://www.premierleague.com/en/news/2174909

``element_type``: 1=GK, 2=DEF, 3=MID, 4=FWD (FPL bootstrap).
"""

from __future__ import annotations

from scipy.stats import poisson

SEASON_LABEL = "2025-26"

__all__ = [
    "SEASON_LABEL",
    "expected_bonus_points_proxy",
    "expected_defensive_contribution_points",
    "expected_goals_conceded_points",
    "points_per_assist",
    "points_per_clean_sheet",
    "points_per_goal",
    "points_per_three_saves",
]


def points_per_goal(element_type: int) -> int:
    """Points for one goal by position."""
    return {1: 10, 2: 6, 3: 5, 4: 4}.get(int(element_type), 4)


def points_per_assist(_element_type: int) -> int:
    """Points for one assist (same for all outfield + GK)."""
    return 3


def points_per_clean_sheet(element_type: int) -> int:
    """CS points by position (FPL needs 60+ mins; we scale elsewhere with minutes)."""
    et = int(element_type)
    if et in (1, 2):
        return 4
    if et == 3:
        return 1
    return 0


def points_per_three_saves(_element_type: int) -> int:
    """GK: one point per three saves (FPL)."""
    return 1


def expected_bonus_points_proxy(
    bonus_points_per_90: float,
    minutes_weight: float,
    *,
    max_per_match: float = 3.0,
) -> float:
    """Rough E[bonus] from season bonus total / minutes, scaled by involvement."""
    rate = max(0.0, float(bonus_points_per_90))
    w = max(0.0, float(minutes_weight))
    return min(float(max_per_match), rate * w)


def expected_defensive_contribution_points(
    element_type: int,
    defensive_actions_per_90: float,
    minutes_weight: float,
) -> float:
    """Linear proxy for 2025/26 DC rule (2 pts when action count crosses threshold).

    Threshold: **10** CBIT for defenders (``element_type`` 2), **12** CBIRT for
    midfielders and forwards (3 and 4). Goalkeepers get 0 here.

    ``defensive_actions_per_90`` is the official static field (actions / 90).
    ``minutes_weight`` is the same involvement shrink/expand as elsewhere.
    """
    et = int(element_type)
    if et not in (2, 3, 4):
        return 0.0
    thresh = 10.0 if et == 2 else 12.0
    z = max(0.0, float(defensive_actions_per_90)) * max(0.0, float(minutes_weight))
    return min(2.0, 2.0 * z / thresh)


def expected_goals_conceded_points(
    opponent_lambda: float,
    *,
    max_goals: int = 50,
) -> float:
    """GK/DEF goals conceded: -1 FPL point per pair of goals conceded (expected).

    Opponent ``G ~ Poisson(λ)``. FPL penalty ``-⌊G/2⌋``. Returns ``-E[⌊G/2⌋]`` (≤ 0).
    """
    lam = max(float(opponent_lambda), 1e-9)
    ev_pairs = 0.0
    for k in range(max_goals + 1):
        ev_pairs += float(poisson.pmf(k, lam)) * (k // 2)
    return -float(ev_pairs)

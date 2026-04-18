"""Fixture-level predicted goals / scorelines (independent Poisson v1)."""

from __future__ import annotations

from scipy.stats import poisson

__all__ = ["best_scoreline", "expected_score_tuple"]


def best_scoreline(
    lam_home: float,
    lam_away: float,
    *,
    max_goals: int = 6,
) -> tuple[tuple[int, int], float]:
    """Most probable (home_goals, away_goals) on a coarse grid."""
    lh = max(float(lam_home), 1e-6)
    la = max(float(lam_away), 1e-6)
    best_h, best_a = 0, 0
    best_p = 0.0
    for h in range(max_goals + 1):
        ph = float(poisson.pmf(h, lh))
        for a in range(max_goals + 1):
            p = ph * float(poisson.pmf(a, la))
            if p > best_p:
                best_p = p
                best_h, best_a = h, a
    return (best_h, best_a), best_p


def expected_score_tuple(lam_home: float, lam_away: float) -> tuple[float, float]:
    """Independent Poisson means (``E[home goals]``, ``E[away goals]``)."""
    return max(float(lam_home), 0.0), max(float(lam_away), 0.0)

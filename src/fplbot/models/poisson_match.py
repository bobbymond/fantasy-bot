"""Independent Poisson marginals (v1)."""

from __future__ import annotations

from scipy.stats import poisson

__all__ = ["clean_sheet_prob", "match_outcome_probs"]


def clean_sheet_prob(opponent_lambda: float) -> float:
    """P(opponent scores 0) when they score ~ Poisson(``opponent_lambda``)."""
    lam = max(float(opponent_lambda), 1e-6)
    return float(poisson.pmf(0, lam))


def match_outcome_probs(
    lam_home: float,
    lam_away: float,
    *,
    max_goals: int = 12,
) -> tuple[float, float, float]:
    """P(home win), P(draw), P(away) from an independent Poisson score grid.

    Uses goals ``0 … max_goals`` inclusive per side; tail mass beyond ``max_goals``
    is omitted (error < ~1e-3 for typical λ).
    """
    lh = max(float(lam_home), 1e-6)
    la = max(float(lam_away), 1e-6)
    p_home = p_draw = p_away = 0.0
    for h in range(max_goals + 1):
        ph = float(poisson.pmf(h, lh))
        for a in range(max_goals + 1):
            pa = float(poisson.pmf(a, la))
            p = ph * pa
            if h > a:
                p_home += p
            elif h == a:
                p_draw += p
            else:
                p_away += p
    s = p_home + p_draw + p_away
    if s <= 0.0:
        return 1 / 3, 1 / 3, 1 / 3
    return p_home / s, p_draw / s, p_away / s

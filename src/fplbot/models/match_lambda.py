"""Expected goals (λ) — multiplicative ratio model (no shrinkage)."""

from __future__ import annotations

from typing import Any

from fplbot.models.team_strength import TeamRateTable
from fplbot.settings import ModelParams

__all__ = ["lambda_breakdown", "lambdas_for_fixture"]


def lambda_breakdown(
    fixture: dict[str, Any],
    rates: TeamRateTable,
) -> dict[str, Any]:
    """Intermediate quantities for ``lambdas_for_fixture`` (for CLI / tests).

    Home/away **split** rates vs ``μ_home`` / ``μ_away`` only — no extra
    ``home_advantage`` scalar and no FDR lift on λ.
    """
    th = int(fixture["team_h"])
    ta = int(fixture["team_a"])
    μh, μa = rates.mu_home, rates.mu_away

    home_attack = rates.gs_home_avg[th] / μh
    away_defense = rates.gc_away_avg[ta] / μa
    lam_h_core = home_attack * away_defense * μh

    away_attack = rates.gs_away_avg[ta] / μa
    home_defense = rates.gc_home_avg[th] / μh
    lam_a_core = away_attack * home_defense * μa

    lam_h_pre = lam_h_core
    lam_a_pre = lam_a_core

    lam_h = max(lam_h_pre, 1e-3)
    lam_a = max(lam_a_pre, 1e-3)

    return {
        "team_h": th,
        "team_a": ta,
        "mu_home": μh,
        "mu_away": μa,
        "home_attack_ratio": home_attack,
        "away_defense_ratio": away_defense,
        "lam_home_core": lam_h_core,
        "away_attack_ratio": away_attack,
        "home_defense_ratio": home_defense,
        "lam_away_core": lam_a_core,
        "lambda_home_pre_floor": lam_h_pre,
        "lambda_away_pre_floor": lam_a_pre,
        "lambda_home": lam_h,
        "lambda_away": lam_a,
    }


def lambdas_for_fixture(
    fixture: dict[str, Any],
    rates: TeamRateTable,
    _model: ModelParams,
) -> tuple[float, float]:
    """Return ``(lambda_home, lambda_away)`` using league averages and team rates.

    ``_model`` is kept for call-site compatibility (strength window etc. already
    baked into ``rates``).

    **Home:** ``λ_home = (gs_home/μ_home) × (gc_away/μ_away) × μ_home``.

    **Away:** ``λ_away = (gs_away/μ_away) × (gc_home/μ_home) × μ_away``.
    """
    d = lambda_breakdown(fixture, rates)
    return float(d["lambda_home"]), float(d["lambda_away"])

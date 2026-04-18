"""Per-team goal rates from finished fixtures (no shrinkage — explicit ratios for λ)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fplbot.settings import ModelParams

__all__ = [
    "TeamRateTable",
    "build_team_rates",
    "league_means_all_finished",
    "venue_totals_all_finished",
]


@dataclass(frozen=True)
class TeamRateTable:
    """League averages and per-team raw goals-for / against rates in the window.

    ``mu_home`` / ``mu_away`` are league mean goals per finished match (home / away).
    Per-team averages impute to those baselines when a side has no games in-window.

    ``goals_*`` and ``n_home`` / ``n_away`` are **raw sums and counts in the same
    window** used for those averages (for CLI transparency — not full-season FPL).

    ``n_fixtures_in_window`` counts finished scored rows used (after GW slice).

    ``n_finished_gws_silver`` is how many distinct GW ids appear among all
    finished scored fixtures in the snapshot (before applying the window cap).
    """

    mu_home: float
    mu_away: float
    gs_home_avg: dict[int, float]
    gc_home_avg: dict[int, float]
    gs_away_avg: dict[int, float]
    gc_away_avg: dict[int, float]
    goals_scored_home: dict[int, float]
    goals_conceded_home: dict[int, float]
    goals_scored_away: dict[int, float]
    goals_conceded_away: dict[int, float]
    n_home: dict[int, int]
    n_away: dict[int, int]
    window_events: tuple[int, ...]
    n_fixtures_in_window: int
    n_finished_gws_silver: int


def _finished_scored_rows(fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in fixtures:
        if not f.get("finished"):
            continue
        ev = f.get("event")
        if ev is None:
            continue
        hs, aws = f.get("team_h_score"), f.get("team_a_score")
        if hs is None or aws is None:
            continue
        out.append(f)
    return out


def league_means_all_finished(
    fixtures: list[dict[str, Any]],
) -> tuple[float, float, int]:
    """League μ_home / μ_away over every finished scored row in silver (no GW cap)."""
    rows = _finished_scored_rows(fixtures)
    if not rows:
        return 1.25, 1.25, 0
    n = len(rows)
    th = sum(int(r["team_h_score"]) for r in rows)
    ta = sum(int(r["team_a_score"]) for r in rows)
    return max(th / n, 1e-3), max(ta / n, 1e-3), n


def venue_totals_all_finished(
    fixtures: list[dict[str, Any]],
    team_id: int,
) -> dict[str, int | float]:
    """Home/away goal sums and counts for ``team_id`` over all finished scored rows."""
    rows = _finished_scored_rows(fixtures)
    n_h = n_a = 0
    gsh = gch = gsa = gca = 0.0
    for r in rows:
        th, ta = int(r["team_h"]), int(r["team_a"])
        hs, aws = int(r["team_h_score"]), int(r["team_a_score"])
        if th == team_id:
            n_h += 1
            gsh += float(hs)
            gch += float(aws)
        if ta == team_id:
            n_a += 1
            gsa += float(aws)
            gca += float(hs)
    return {
        "n_home": n_h,
        "goals_scored_home": gsh,
        "goals_conceded_home": gch,
        "n_away": n_a,
        "goals_scored_away": gsa,
        "goals_conceded_away": gca,
    }


def _window_event_ids(rows: list[dict[str, Any]], max_events: int) -> list[int]:
    """Last ``max_events`` distinct GW ids.

    If ``max_events <= 0``, use every GW present in ``rows``.
    """
    ids = sorted({int(r["event"]) for r in rows})
    if not ids:
        return []
    if max_events <= 0:
        return ids
    return ids[-max_events:]


def build_team_rates(
    fixtures: list[dict[str, Any]],
    team_ids: list[int],
    model: ModelParams,
) -> TeamRateTable:
    """Aggregate goals in the rolling window → averages for λ ratio model."""
    rows = _finished_scored_rows(fixtures)
    n_finished_gws_silver = len({int(r["event"]) for r in rows})
    window = _window_event_ids(rows, model.strength_window_gw)
    window_rows = [r for r in rows if int(r["event"]) in set(window)]

    teams = set(team_ids)
    gs_home = {t: 0.0 for t in teams}
    ga_home = {t: 0.0 for t in teams}
    n_home = {t: 0 for t in teams}
    gs_away = {t: 0.0 for t in teams}
    ga_away = {t: 0.0 for t in teams}
    n_away = {t: 0 for t in teams}

    total_h_goals = 0.0
    total_a_goals = 0.0
    n_fix = 0
    for r in window_rows:
        th, ta = int(r["team_h"]), int(r["team_a"])
        hs, aws = int(r["team_h_score"]), int(r["team_a_score"])
        total_h_goals += hs
        total_a_goals += aws
        n_fix += 1
        gs_home[th] = gs_home.get(th, 0.0) + hs
        ga_home[th] = ga_home.get(th, 0.0) + aws
        n_home[th] = n_home.get(th, 0) + 1
        gs_away[ta] = gs_away.get(ta, 0.0) + aws
        ga_away[ta] = ga_away.get(ta, 0.0) + hs
        n_away[ta] = n_away.get(ta, 0) + 1

    if n_fix == 0:
        μ_h = μ_a = 1.25
        n_rows = 0
    else:
        μ_h = max(total_h_goals / n_fix, 1e-3)
        μ_a = max(total_a_goals / n_fix, 1e-3)
        n_rows = n_fix

    gs_home_avg: dict[int, float] = {}
    gc_home_avg: dict[int, float] = {}
    gs_away_avg: dict[int, float] = {}
    gc_away_avg: dict[int, float] = {}

    for t in teams:
        if n_home.get(t, 0) > 0:
            gs_home_avg[t] = gs_home.get(t, 0.0) / n_home[t]
            gc_home_avg[t] = ga_home.get(t, 0.0) / n_home[t]
        else:
            gs_home_avg[t] = μ_h
            gc_home_avg[t] = μ_a
        if n_away.get(t, 0) > 0:
            gs_away_avg[t] = gs_away.get(t, 0.0) / n_away[t]
            gc_away_avg[t] = ga_away.get(t, 0.0) / n_away[t]
        else:
            gs_away_avg[t] = μ_a
            gc_away_avg[t] = μ_h

    return TeamRateTable(
        mu_home=μ_h,
        mu_away=μ_a,
        gs_home_avg=dict(gs_home_avg),
        gc_home_avg=dict(gc_home_avg),
        gs_away_avg=dict(gs_away_avg),
        gc_away_avg=dict(gc_away_avg),
        goals_scored_home=dict(gs_home),
        goals_conceded_home=dict(ga_home),
        goals_scored_away=dict(gs_away),
        goals_conceded_away=dict(ga_away),
        n_home=dict(n_home),
        n_away=dict(n_away),
        window_events=tuple(window),
        n_fixtures_in_window=n_rows,
        n_finished_gws_silver=n_finished_gws_silver,
    )

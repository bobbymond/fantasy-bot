"""End-to-end projection for one gameweek."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fplbot.models.fixture_scores import best_scoreline, expected_score_tuple
from fplbot.models.fpl_expected_points import (
    FPLPointsBreakdown,
    project_fpl_points_for_fixture,
)
from fplbot.models.match_lambda import lambdas_for_fixture
from fplbot.models.player_points import position_short_label
from fplbot.models.poisson_match import match_outcome_probs
from fplbot.models.silver_io import SilverSnapshot, load_silver, resolve_target_gw
from fplbot.models.team_strength import TeamRateTable, build_team_rates
from fplbot.settings import ModelParams

__all__ = [
    "FixtureScorePrediction",
    "FixtureStrengthMeta",
    "FPLPointsBreakdown",
    "PlayerProjection",
    "project_fixture_scores",
    "project_gw",
    "strength_meta_from_rates",
]


@dataclass(frozen=True)
class FixtureStrengthMeta:
    """Diagnostics for how team strengths were estimated (rolling GW window)."""

    strength_window_gw: int
    n_distinct_gws_in_window: int
    n_finished_gws_silver: int
    gameweek_min: int | None
    gameweek_max: int | None
    n_fixtures_in_window: int
    mu_home: float
    mu_away: float
    window_uses_all_finished_gws: bool


@dataclass(frozen=True)
class FixtureScorePrediction:
    """One unfinished fixture in the target GW."""

    fixture_id: int
    gameweek_id: int
    team_h: int
    team_a: int
    team_h_name: str
    team_a_name: str
    lambda_home: float
    lambda_away: float
    expected_home_goals: float
    expected_away_goals: float
    mode_home_goals: int
    mode_away_goals: int
    mode_scoreline_prob: float
    prob_home_win: float
    prob_draw: float
    prob_away_win: float


@dataclass(frozen=True)
class PlayerProjection:
    player_id: int
    web_name: str
    team_id: int
    team_short: str
    position: str
    opp_short: str
    element_type: int
    xP_fpl: float
    ep_next_fpl: float
    fixture_id: int
    side: str
    breakdown: FPLPointsBreakdown


def _snap_and_rates(
    silver_dir: Path,
    model: ModelParams,
    *,
    gw: int | None,
) -> tuple[SilverSnapshot, int, TeamRateTable]:
    """Shared load: silver snapshot, resolved GW id, team rate table."""
    snap = load_silver(silver_dir)
    gw_id = resolve_target_gw(snap.events, gw_override=gw)
    team_ids = [int(t["id"]) for t in snap.teams]
    rates = build_team_rates(snap.fixtures, team_ids, model, silver_dir, gw_id)
    return snap, gw_id, rates


def _strength_meta(rates: TeamRateTable, model: ModelParams) -> FixtureStrengthMeta:
    ev = rates.window_events
    gmin, gmax = (int(ev[0]), int(ev[-1])) if ev else (None, None)
    n_fin = rates.n_finished_gws_silver
    window_all = len(ev) == n_fin and n_fin > 0
    return FixtureStrengthMeta(
        strength_window_gw=model.strength_window_gw,
        n_distinct_gws_in_window=len(ev),
        n_finished_gws_silver=rates.n_finished_gws_silver,
        gameweek_min=gmin,
        gameweek_max=gmax,
        n_fixtures_in_window=rates.n_fixtures_in_window,
        mu_home=rates.mu_home,
        mu_away=rates.mu_away,
        window_uses_all_finished_gws=window_all,
    )


def strength_meta_from_rates(
    rates: TeamRateTable,
    model: ModelParams,
) -> FixtureStrengthMeta:
    """Public helper for CLI / commands that already built ``rates``."""
    return _strength_meta(rates, model)


def project_fixture_scores(
    silver_dir: Path,
    model: ModelParams,
    *,
    gw: int | None = None,
) -> tuple[int, list[FixtureScorePrediction], FixtureStrengthMeta]:
    """Upcoming (unfinished) fixtures in the target GW with λ and likely scoreline."""
    snap, gw_id, rates = _snap_and_rates(silver_dir, model, gw=gw)
    team_lookup: dict[int, str] = {}
    for t in snap.teams:
        tid = int(t["id"])
        label = str(t.get("short_name") or t.get("name") or "?")
        team_lookup[tid] = label

    out: list[FixtureScorePrediction] = []
    for fx in snap.fixtures:
        if int(fx.get("event") or -1) != gw_id:
            continue
        if fx.get("finished"):
            continue
        th, ta = int(fx["team_h"]), int(fx["team_a"])
        lam_h, lam_a = lambdas_for_fixture(fx, rates, model)
        eh, ea = expected_score_tuple(lam_h, lam_a)
        (mh, ma), mp = best_scoreline(lam_h, lam_a)
        ph, pd, pa = match_outcome_probs(lam_h, lam_a)
        out.append(
            FixtureScorePrediction(
                fixture_id=int(fx["id"]),
                gameweek_id=gw_id,
                team_h=th,
                team_a=ta,
                team_h_name=team_lookup.get(th, str(th)),
                team_a_name=team_lookup.get(ta, str(ta)),
                lambda_home=lam_h,
                lambda_away=lam_a,
                expected_home_goals=eh,
                expected_away_goals=ea,
                mode_home_goals=mh,
                mode_away_goals=ma,
                mode_scoreline_prob=mp,
                prob_home_win=ph,
                prob_draw=pd,
                prob_away_win=pa,
            )
        )
    out.sort(key=lambda r: r.fixture_id)
    return gw_id, out, _strength_meta(rates, model)


def project_gw(
    silver_dir: Path,
    model: ModelParams,
    *,
    gw: int | None = None,
) -> tuple[int, list[PlayerProjection]]:
    """Load silver, resolve GW, return projections sorted by ``xP_fpl`` descending."""
    snap, gw_id, rates = _snap_and_rates(silver_dir, model, gw=gw)

    team_lookup: dict[int, str] = {}
    for t in snap.teams:
        tid = int(t["id"])
        team_lookup[tid] = str(t.get("short_name") or t.get("name") or "?")

    rows: list[PlayerProjection] = []
    for fx in snap.fixtures:
        if int(fx.get("event") or -1) != gw_id:
            continue
        lam_h, lam_a = lambdas_for_fixture(fx, rates, model)
        raw = project_fpl_points_for_fixture(
            snap.players,
            fx,
            fixtures=snap.fixtures,
            lambda_home=lam_h,
            lambda_away=lam_a,
        )
        fid = int(fx["id"])
        th, ta = int(fx["team_h"]), int(fx["team_a"])
        for r in raw:
            tid = int(r["team_id"])
            opp_id = ta if tid == th else th
            bd: FPLPointsBreakdown = r["breakdown"]
            et_row = int(r["element_type"])
            rows.append(
                PlayerProjection(
                    player_id=int(r["player_id"]),
                    web_name=str(r["web_name"]),
                    team_id=tid,
                    team_short=team_lookup.get(tid, str(tid)),
                    position=position_short_label(et_row),
                    opp_short=team_lookup.get(opp_id, str(opp_id)),
                    element_type=et_row,
                    xP_fpl=float(r["xP_fpl"]),
                    ep_next_fpl=float(r["ep_next_fpl"]),
                    fixture_id=fid,
                    side=str(r["side"]),
                    breakdown=bd,
                )
            )

    rows.sort(key=lambda r: r.xP_fpl, reverse=True)
    return gw_id, rows

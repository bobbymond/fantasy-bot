"""Expected FPL points per player for one fixture (see ``fpl_scoring_2526``)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fplbot.models.fpl_scoring_2526 import (
    expected_bonus_points_proxy,
    expected_defensive_contribution_points,
    expected_goals_conceded_points,
    points_per_assist,
    points_per_clean_sheet,
    points_per_goal,
)
from fplbot.models.player_points import (
    _attack_weight,
    _bonus_points_per_90,
    _defensive_actions_per_90,
    _float,
    _minutes_share,
    is_hard_unavailable,
    team_finished_fixture_counts,
)
from fplbot.models.poisson_match import clean_sheet_prob
from fplbot.models.season_snapshot_stats import league_goals_assists_totals

__all__ = ["FPLPointsBreakdown", "project_fpl_points_for_fixture"]


@dataclass(frozen=True)
class FPLPointsBreakdown:
    """FPL bucket expectations + a few model internals for ``--breakdown``."""

    appearance: float
    goals: float
    assists: float
    clean_sheet: float
    goals_conceded: float
    saves: float
    defensive_contrib: float
    cards: float
    bonus: float
    team_lambda: float
    opp_lambda: float
    p_clean_sheet: float
    minutes_w: float
    goal_share: float
    assist_share: float
    assist_scale: float


def project_fpl_points_for_fixture(
    players: list[dict[str, Any]],
    fixture: dict[str, Any],
    *,
    fixtures: list[dict[str, Any]],
    lambda_home: float,
    lambda_away: float,
) -> list[dict[str, Any]]:
    """Each squad player: total ``xP_fpl`` and a ``FPLPointsBreakdown``."""
    th = int(fixture["team_h"])
    ta = int(fixture["team_a"])
    team_fixture_n = team_finished_fixture_counts(fixtures)
    league = league_goals_assists_totals(players)
    assist_scale = (
        league.assists_per_goal if league.goals_scored > 0 else 0.95
    )
    p_cs_h = clean_sheet_prob(lambda_away)
    p_cs_a = clean_sheet_prob(lambda_home)

    out: list[dict[str, Any]] = []
    for side, tid, lam_for, lam_opp, p_cs in (
        ("H", th, lambda_home, lambda_away, p_cs_h),
        ("A", ta, lambda_away, lambda_home, p_cs_a),
    ):
        squad = [p for p in players if int(p["team"]) == tid]
        if not squad:
            continue
        n_team_finished = team_fixture_n.get(tid, 0)
        alloc = [p for p in squad if not is_hard_unavailable(p)]
        if not alloc:
            alloc = squad
        wsum = sum(_attack_weight(p) for p in alloc)
        n_def_unit = max(
            1,
            sum(1 for p in alloc if int(p.get("element_type", 0)) in (1, 2)),
        )
        xg_sum = sum(max(_float(p.get("expected_goals")), 0.0) for p in alloc)
        xa_sum = sum(max(_float(p.get("expected_assists")), 0.0) for p in alloc)
        team_concede_ev = expected_goals_conceded_points(lam_opp)
        def_indices = [p for p in alloc if int(p.get("element_type", 0)) in (1, 2)]
        ms_def_sum = (
            sum(
                _minutes_share(p, team_completed_fixtures=n_team_finished)
                for p in def_indices
            )
            or 1.0
        )

        for p in squad:
            et = int(p.get("element_type", 0))
            wname = str(p.get("web_name") or p.get("second_name") or "")
            if is_hard_unavailable(p):
                bd0 = FPLPointsBreakdown(
                    appearance=0.0,
                    goals=0.0,
                    assists=0.0,
                    clean_sheet=0.0,
                    goals_conceded=0.0,
                    saves=0.0,
                    defensive_contrib=0.0,
                    cards=0.0,
                    bonus=0.0,
                    team_lambda=float(lam_for),
                    opp_lambda=float(lam_opp),
                    p_clean_sheet=float(p_cs),
                    minutes_w=0.0,
                    goal_share=0.0,
                    assist_share=0.0,
                    assist_scale=float(assist_scale),
                )
                out.append(
                    {
                        "player_id": int(p["id"]),
                        "web_name": wname,
                        "team_id": tid,
                        "element_type": et,
                        "side": side,
                        "xP_fpl": 0.0,
                        "ep_next_fpl": _float(p.get("ep_next"), 0.0),
                        "breakdown": bd0,
                    }
                )
                continue

            ms = _minutes_share(p, team_completed_fixtures=n_team_finished)
            w = _attack_weight(p)
            share = w / wsum if wsum > 1e-9 else 0.0
            xg_p = max(_float(p.get("expected_goals")), 0.0)
            xa_p = max(_float(p.get("expected_assists")), 0.0)
            share_g = (xg_p / xg_sum) if xg_sum > 1e-9 else share
            share_a = (xa_p / xa_sum) if xa_sum > 1e-9 else share
            goal_share = 0.5 * share + 0.5 * share_g
            e_goals = lam_for * goal_share
            pts_goals = float(points_per_goal(et)) * e_goals

            # Team assist "budget": λ × (Σassists/Σgoals on silver).
            assist_mass = lam_for * assist_scale
            e_assists = assist_mass * share_a
            pts_assists = float(points_per_assist(et)) * e_assists

            e_app = min(2.0, 1.0 + ms)

            if et in (1, 2):
                e_cs = float(points_per_clean_sheet(et)) * p_cs * ms / float(n_def_unit)
            elif et == 3:
                e_cs = float(points_per_clean_sheet(3)) * p_cs * ms
            else:
                e_cs = 0.0

            if et in (1, 2):
                gc = team_concede_ev * (ms / ms_def_sum)
            else:
                gc = 0.0

            saves = 0.0
            def_contrib = expected_defensive_contribution_points(
                et, _defensive_actions_per_90(p), ms
            )
            cards = 0.0
            bonus = expected_bonus_points_proxy(_bonus_points_per_90(p), ms)

            xP_fpl = (
                e_app
                + pts_goals
                + pts_assists
                + e_cs
                + gc
                + saves
                + def_contrib
                + cards
                + bonus
            )

            bd = FPLPointsBreakdown(
                appearance=e_app,
                goals=pts_goals,
                assists=pts_assists,
                clean_sheet=e_cs,
                goals_conceded=gc,
                saves=saves,
                defensive_contrib=def_contrib,
                cards=cards,
                bonus=bonus,
                team_lambda=float(lam_for),
                opp_lambda=float(lam_opp),
                p_clean_sheet=float(p_cs),
                minutes_w=float(ms),
                goal_share=float(goal_share),
                assist_share=float(share_a),
                assist_scale=float(assist_scale),
            )
            out.append(
                {
                    "player_id": int(p["id"]),
                    "web_name": wname,
                    "team_id": tid,
                    "element_type": et,
                    "side": side,
                    "xP_fpl": float(xP_fpl),
                    "ep_next_fpl": _float(p.get("ep_next"), 0.0),
                    "breakdown": bd,
                }
            )
    return out

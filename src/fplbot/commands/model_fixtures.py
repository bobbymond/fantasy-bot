"""Fixture-level score predictions for upcoming (unfinished) matches."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fplbot.models.fixture_scores import best_scoreline, expected_score_tuple
from fplbot.models.match_lambda import lambda_breakdown, lambdas_for_fixture
from fplbot.models.pipeline import (
    FixtureScorePrediction,
    FixtureStrengthMeta,
    project_fixture_scores,
    strength_meta_from_rates,
)
from fplbot.models.poisson_match import match_outcome_probs
from fplbot.models.silver_io import load_silver
from fplbot.models.team_strength import (
    TeamRateTable,
    build_team_rates,
    league_means_all_finished,
    venue_totals_all_finished,
)
from fplbot.settings import ModelParams, load_app_config

__all__ = [
    "FixtureScorePrediction",
    "FixtureStrengthMeta",
    "format_fixture_compact_hint_line",
    "format_fixture_deep_breakdown_lines",
    "run",
    "run_fixture_detail",
]


def format_fixture_compact_hint_line(pred: dict[str, Any]) -> str:
    """One line pointing at ``model fixture`` for the full window + λ trace."""
    fid = int(pred["fixture_id"])
    gwe = int(pred["gameweek_id"])
    return f"       detail: fplbot model fixture {fid} --gw {gwe}"


def _pred_dict_from_fixture(
    fx: dict[str, Any],
    rates: TeamRateTable,
    model: ModelParams,
    team_lookup: dict[int, str],
) -> dict[str, Any]:
    th, ta = int(fx["team_h"]), int(fx["team_a"])
    lam_h, lam_a = lambdas_for_fixture(fx, rates, model)
    eh, ea = expected_score_tuple(lam_h, lam_a)
    (mh, ma), mp = best_scoreline(lam_h, lam_a)
    ph, pd, pa = match_outcome_probs(lam_h, lam_a)
    return {
        "fixture_id": int(fx["id"]),
        "gameweek_id": int(fx["event"]),
        "team_h": th,
        "team_a": ta,
        "team_h_name": team_lookup.get(th, str(th)),
        "team_a_name": team_lookup.get(ta, str(ta)),
        "lambda_home": lam_h,
        "lambda_away": lam_a,
        "expected_home_goals": eh,
        "expected_away_goals": ea,
        "mode_home_goals": mh,
        "mode_away_goals": ma,
        "mode_scoreline_prob": mp,
        "prob_home_win": ph,
        "prob_draw": pd,
        "prob_away_win": pa,
        "finished": bool(fx.get("finished")),
    }


def _defence_vs_league(value: float, baseline: float, *, eps: float = 0.02) -> str:
    if value > baseline * (1.0 + eps):
        return "leakier than typical"
    if value < baseline * (1.0 - eps):
        return "tighter than typical"
    return "about typical"


def _lambda_floor_suffix(pre: float, final: float) -> str:
    if abs(pre - final) < 1e-12:
        return f"→ λ={final:.4f}"
    return f"→ λ_pre={pre:.4f} (floor → {final:.4f})"


def _season_team_lines(
    title: str,
    tid: int,
    fixtures: list[dict[str, Any]],
    mu_home_all: float,
    mu_away_all: float,
) -> list[str]:
    """Full-silver snapshot vs league μ (same file, all finished rows)."""
    t = venue_totals_all_finished(fixtures, tid)
    nh = int(t["n_home"])
    na = int(t["n_away"])
    gsh = float(t["goals_scored_home"])
    gch = float(t["goals_conceded_home"])
    gsa = float(t["goals_scored_away"])
    gca = float(t["goals_conceded_away"])
    lines = [f"         {title} (team id {tid}), all finished rows in silver:"]
    if nh > 0:
        gah = gch / float(nh)
        cmp_h = _defence_vs_league(gah, mu_away_all)
        gsf = gsh / float(nh)
        lines.append(
            f"           Home: n={nh}  GF={gsh:.0f} ({gsf:.3f}/gm); "
            f"μ_home={mu_home_all:.3f}"
        )
        lines.append(
            f"           GA={gch:.0f} ({gah:.3f}/gm at home); μ_away={mu_away_all:.3f} "
            f"→ {cmp_h} at home"
        )
    else:
        lines.append("           Home: n=0 finished games in silver")
    if na > 0:
        gaa = gca / float(na)
        cmp_a = _defence_vs_league(gaa, mu_home_all)
        gas = gsa / float(na)
        lines.append(
            f"           Away: n={na}  GF={gsa:.0f} ({gas:.3f}/gm); "
            f"μ_away={mu_away_all:.3f}"
        )
        lines.append(
            f"           GA={gca:.0f} ({gaa:.3f}/gm away); μ_home={mu_home_all:.3f} "
            f"→ {cmp_a} on the road"
        )
    else:
        lines.append("           Away: n=0 finished games in silver")
    return lines


def _team_window_lines(
    title: str,
    tid: int,
    rates: TeamRateTable,
) -> list[str]:
    nh = rates.n_home.get(tid, 0)
    na = rates.n_away.get(tid, 0)
    gsh = rates.goals_scored_home.get(tid, 0.0)
    gch = rates.goals_conceded_home.get(tid, 0.0)
    gsa = rates.goals_scored_away.get(tid, 0.0)
    gca = rates.goals_conceded_away.get(tid, 0.0)
    ghs = rates.gs_home_avg.get(tid, 0.0)
    gchm = rates.gc_home_avg.get(tid, 0.0)
    gas = rates.gs_away_avg.get(tid, 0.0)
    gcam = rates.gc_away_avg.get(tid, 0.0)
    lines = [f"         {title} (team id {tid}):"]
    if nh > 0:
        lines.append(
            f"           Home games in window: n={nh}  "
            f"GF={gsh:.0f} ({gsh / nh:.3f}/gm)  "
            f"GA={gch:.0f} ({gch / nh:.3f}/gm)  "
            f"→ gs_home_avg={ghs:.3f}  gc_home_avg={gchm:.3f}"
        )
    else:
        lines.append(
            "           Home games in window: n=0  "
            f"(imputed gs_home_avg={ghs:.3f}, gc_home_avg={gchm:.3f})"
        )
    if na > 0:
        lines.append(
            f"           Away games in window: n={na}  "
            f"GF={gsa:.0f} ({gsa / na:.3f}/gm)  "
            f"GA={gca:.0f} ({gca / na:.3f}/gm)  "
            f"→ gs_away_avg={gas:.3f}  gc_away_avg={gcam:.3f}"
        )
    else:
        lines.append(
            "           Away games in window: n=0  "
            f"(imputed gs_away_avg={gas:.3f}, gc_away_avg={gcam:.3f})"
        )
    return lines


def format_fixture_deep_breakdown_lines(
    pred: dict[str, Any],
    lb: dict[str, Any],
    rates: TeamRateTable,
    meta: dict[str, Any],
    all_fixtures: list[dict[str, Any]],
) -> list[str]:
    """Full trace for ``model fixture``: silver-wide snapshot, window, λ."""
    lam_h = float(pred["lambda_home"])
    lam_a = float(pred["lambda_away"])
    eh, ea = expected_score_tuple(lam_h, lam_a)
    (mh, ma), mp = best_scoreline(lam_h, lam_a)
    ph, pd, pa = match_outcome_probs(lam_h, lam_a)
    th = int(pred["team_h"])
    ta = int(pred["team_a"])
    thn = str(pred.get("team_h_name") or th)
    tan = str(pred.get("team_a_name") or ta)
    n_w = int(rates.n_fixtures_in_window)
    uh, ua = float(lb["mu_home"]), float(lb["mu_away"])
    tot_h = uh * float(n_w)
    tot_a = ua * float(n_w)
    sw = int(meta["strength_window_gw"])
    gmin, gmax = meta.get("gameweek_min"), meta.get("gameweek_max")
    span = f"{gmin}–{gmax}" if gmin is not None else "—"
    fin = "finished" if pred.get("finished") else "not finished"
    muh_all, mua_all, n_all = league_means_all_finished(all_fixtures)
    lines: list[str] = [
        f"       fixture {int(pred['fixture_id'])} GW{int(pred['gameweek_id'])} "
        f"({thn} vs {tan})  [{fin}]",
        (
            "         A) All finished matches in this silver file "
            "(context only; λ ignores this):"
        ),
        (
            f"           League over n={n_all} matches: μ_home={muh_all:.3f}  "
            f"μ_away={mua_all:.3f}"
            if n_all
            else "           League: no finished scored rows in silver"
        ),
    ]
    if n_all:
        lines.extend(_season_team_lines(thn, th, all_fixtures, muh_all, mua_all))
        lines.extend(_season_team_lines(tan, ta, all_fixtures, muh_all, mua_all))
    b_intro = (
        "         B) Rates for λ (strength_window_gw=0 → every finished GW; "
        "same span as (A) above):"
        if sw == 0
        else (
            "         B) Strength window for λ (last strength_window_gw="
            f"{sw} GW ids {span}):"
        )
    )
    lines.extend(
        [
            b_intro,
            f"         League (n={n_w} finished scored matches in window):",
            (
                f"           μ_home={uh:.3f} (= Σ home goals / n = {tot_h:.1f}/{n_w})"
                if n_w
                else f"           μ_home={uh:.3f} (no finished rows in window)"
            ),
            (
                f"           μ_away={ua:.3f} (= Σ away goals / n = {tot_a:.1f}/{n_w})"
                if n_w
                else f"           μ_away={ua:.3f} (no finished rows in window)"
            ),
        ]
    )
    lines.extend(_team_window_lines(thn, th, rates))
    lines.extend(_team_window_lines(tan, ta, rates))
    har = float(lb["home_attack_ratio"])
    adr = float(lb["away_defense_ratio"])
    muh = float(lb["mu_home"])
    lhc = float(lb["lam_home_core"])
    lhp = float(lb["lambda_home_pre_floor"])
    lhf = float(lb["lambda_home"])
    aar = float(lb["away_attack_ratio"])
    hdr = float(lb["home_defense_ratio"])
    mua = float(lb["mu_away"])
    lac = float(lb["lam_away_core"])
    lap = float(lb["lambda_away_pre_floor"])
    laf = float(lb["lambda_away"])
    tail_h = _lambda_floor_suffix(lhp, lhf)
    tail_a = _lambda_floor_suffix(lap, laf)
    lines.extend(
        [
            f"         Home λ ({thn} at home × {tan} away defence × μ_home):",
            "           (gs_home/μ_home)×(gc_away/μ_away)×μ_home "
            f"= {har:.3f}×{adr:.3f}×{muh:.3f} → {lhc:.4f}  {tail_h}",
            f"             gs_home/μ_home from {thn} home row; "
            f"gc_away/μ_away from {tan} away (GA/gm / μ_away).",
            f"         Away λ ({tan} away × {thn} home defence × μ_away):",
            "           (gs_away/μ_away)×(gc_home/μ_home)×μ_away "
            f"= {aar:.3f}×{hdr:.3f}×{mua:.3f} → {lac:.4f}  {tail_a}",
            f"             gc_home/μ_home = gc_home_avg({thn})/μ_home "
            f"(in-window home games only — not season GA).",
            "         E[goals] (independent Poisson means): "
            f"{eh:.3f}–{ea:.3f} (= λ_home–λ_away)",
            "         Mode scoreline: search h,a ∈ [0..6] for max P(H=h)P(A=a); "
            f"best {mh}-{ma} (p={mp:.4f})",
            "         1X2: sum joint grid h,a ∈ [0..12] (tail trimmed); "
            f"H={100 * ph:.1f}% D={100 * pd:.1f}% A={100 * pa:.1f}%",
        ]
    )
    return lines


def run_fixture_detail(
    *,
    fixture_id: int,
    gw: int | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    TeamRateTable,
    dict[str, Any],
    list[dict[str, Any]],
]:
    """Load silver; return pred, λ breakdown, rates, meta, fixtures list."""
    cfg = load_app_config()
    snap = load_silver(cfg.paths.silver)
    fx_row = next((f for f in snap.fixtures if int(f["id"]) == fixture_id), None)
    if fx_row is None:
        raise ValueError(f"No fixture id={fixture_id} in silver fixtures")
    fx_ev = int(fx_row.get("event") or -1)
    if fx_ev < 0:
        raise ValueError(f"Fixture {fixture_id} has no event (gameweek) set")
    if gw is not None and gw != fx_ev:
        raise ValueError(
            f"Fixture {fixture_id} is in GW{fx_ev}, not --gw {gw} (omit --gw to allow)"
        )
    team_ids = [int(t["id"]) for t in snap.teams]
    rates = build_team_rates(snap.fixtures, team_ids, cfg.model, cfg.paths.silver, fx_ev)
    team_lookup = {
        int(t["id"]): str(t.get("short_name") or t.get("name") or "?")
        for t in snap.teams
    }
    pred = _pred_dict_from_fixture(fx_row, rates, cfg.model, team_lookup)
    lb = lambda_breakdown(fx_row, rates)
    meta = strength_meta_from_rates(rates, cfg.model)
    return pred, lb, rates, asdict(meta), snap.fixtures


def run(
    *,
    gw: int | None = None,
) -> tuple[int, list[dict[str, object]], dict[str, object]]:
    """Return ``(gw_id, rows, strength_meta)``.

    For per-fixture window totals + λ, use ``run_fixture_detail``.
    """
    cfg = load_app_config()
    gw_id, preds, meta = project_fixture_scores(cfg.paths.silver, cfg.model, gw=gw)
    rows = [asdict(r) for r in preds]
    return gw_id, rows, asdict(meta)

"""Load projection for one GW and return one player's row (full list, not top-N)."""

from __future__ import annotations

import textwrap
from dataclasses import asdict
from typing import Any

from fplbot.models.fpl_scoring_2526 import (
    SEASON_LABEL,
    points_per_assist,
    points_per_clean_sheet,
    points_per_goal,
)
from fplbot.models.pipeline import project_gw
from fplbot.models.player_points import position_short_label
from fplbot.models.season_snapshot_stats import read_players_rows
from fplbot.settings import load_app_config


def _fpl_static_from_silver_row(pel: dict[str, Any]) -> dict[str, Any]:
    """Subset of silver ``players`` row used for probe-player narrative."""
    return {
        "fpl_status": pel.get("status"),
        "fpl_news": pel.get("news"),
        "fpl_news_added": pel.get("news_added"),
        "fpl_chance_this_round": pel.get("chance_of_playing_this_round"),
        "fpl_chance_next_round": pel.get("chance_of_playing_next_round"),
    }


def _fmt_pct(v: Any) -> str:
    if v is None or v == "":
        return "— (null / not set in this silver snapshot)"
    try:
        n = int(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{n}% (FPL estimate for that API GW label)"


def _fpl_static_availability_lines(row: dict[str, Any]) -> list[str]:
    """Bootstrap injury/availability; only ``status`` drives hard-zero xP today."""
    st = row.get("fpl_status")
    c_this = row.get("fpl_chance_this_round")
    c_next = row.get("fpl_chance_next_round")
    news = row.get("fpl_news") or ""
    added = row.get("fpl_news_added")

    hdr = "— FPL static from silver (bootstrap → players.parquet) —"
    status_leg = (
        "    (a=available, d=doubtful, i=injured, s=suspended, u=unavailable, "
        "n=not next GW — check FPL copy.)"
    )
    cthis_leg = (
        "    (FPL “this” GW in the API snapshot — may differ from probe --gw.)"
    )
    cnext_leg = "    (FPL “next” GW in that same snapshot.)"
    lines = [
        "",
        hdr,
        f"  status:                 {st if st is not None and str(st) != '' else '—'}",
        status_leg,
        "  chance_of_playing_this_round:",
        f"    {_fmt_pct(c_this)}",
        cthis_leg,
        "  chance_of_playing_next_round:",
        f"    {_fmt_pct(c_next)}",
        cnext_leg,
    ]
    if added is not None and str(added).strip():
        lines.append(f"  news_added:             {added}")
    if str(news).strip():
        lines.append("  news:")
        lines.extend(
            textwrap.wrap(
                str(news).strip(),
                width=86,
                initial_indent="    ",
                subsequent_indent="    ",
            )
        )
    else:
        lines.append("  news:                   — (empty)")
    return lines


def run(*, player_id: int, gw: int | None = None) -> tuple[int, dict[str, Any]]:
    """Return ``(gw_id, row_dict)`` for one player in that GW.

    Raises ``LookupError`` if the element is not in any fixture squad this GW.
    """
    cfg = load_app_config()
    silver = cfg.paths.silver
    gw_id, rows = project_gw(silver, cfg.model, gw=gw)
    pid = int(player_id)
    pel: dict[str, Any] = {}
    try:
        for pr in read_players_rows(silver / "players.parquet"):
            if int(pr.get("id", -1)) == pid:
                pel = pr
                break
    except FileNotFoundError:
        pel = {}
    for r in rows:
        if int(r.player_id) == pid:
            row = asdict(r)
            row.update(_fpl_static_from_silver_row(pel))
            return gw_id, row
    msg = f"no player_id={pid} in gameweek {gw_id} (not in a fixture squad this GW)"
    raise LookupError(msg)


def verbose_breakdown_lines(gw_id: int, row: dict[str, Any]) -> list[str]:
    """Human-readable explanation of ``xP_fpl`` (one string per line, no typer)."""
    bd = row["breakdown"]
    et = int(row["element_type"])
    et_name = {1: "Goalkeeper", 2: "Defender", 3: "Midfielder", 4: "Forward"}.get(
        et, f"element_type {et}"
    )
    ppg = points_per_goal(et)
    ppa = points_per_assist(et)
    pcs_rule = points_per_clean_sheet(et)

    name = str(row.get("web_name") or "?")
    pid = int(row["player_id"])
    pos = str(row.get("position") or position_short_label(et))
    lines: list[str] = [
        f"Player: {name} ({pos}) — element id {pid} ({et_name})",
        f"Gameweek: {gw_id}  |  Fixture id {int(row['fixture_id'])}  |  "
        f"{row['team_short']} vs {row['opp_short']} ({row['side']} = "
        f"{'home' if row['side'] == 'H' else 'away'})",
        "",
        f"Ruleset: FPL {SEASON_LABEL} (see fplbot.models.fpl_scoring_2526).",
        f"FPL official ep_next on this row in silver: {float(row['ep_next_fpl']):.2f} "
        "(not recomputed by us).",
    ]
    lines.extend(_fpl_static_availability_lines(row))
    lines += [
        "",
        f"Total model xP_fpl: {float(row['xP_fpl']):.3f}",
        "",
        "— FPL point buckets (expected contribution each) —",
    ]

    def _ln(label: str, val: float, expl: str) -> None:
        lines.append(f"  {label + ':':<22} {val:>7.3f}  {expl}")

    _ln(
        "Appearance",
        float(bd["appearance"]),
        "v1 proxy min(2, 1 + minutes_w); minutes_w = season minutes / "
        "(90 × team's finished fixture count from silver), floor 0.08 cap 1 "
        "(not true P(60+) yet — see TASKS Later § minutes). "
        "Bootstrap ``status`` i/s/n/u → 0 xP_fpl (hard unavailable).",
    )
    lam_t = float(bd["team_lambda"])
    gsh = float(bd["goal_share"])
    _ln(
        "Goals",
        float(bd["goals"]),
        f"team λ={lam_t:.3f} × goal_share={gsh:.3f} × {ppg} pts/goal.",
    )
    asc = float(bd["assist_scale"])
    _ln(
        "Assists",
        float(bd["assists"]),
        f"assist_scale={asc:.3f} (Σast/Σg on silver; else 0.95); "
        f"e_assists=λ×assist_scale×assist_share "
        f"(assist_share={float(bd['assist_share']):.3f}) × {ppa} pts/assist.",
    )
    _ln(
        "Clean sheet",
        float(bd["clean_sheet"]),
        f"P(opp scores 0)={float(bd['p_clean_sheet']):.3f}; position CS value "
        f"{pcs_rule} scaled by minutes / DEF split rules.",
    )
    gc = float(bd["goals_conceded"])
    if et in (1, 2):
        _ln(
            "Goals conceded",
            gc,
            "GK/DEF only: share of team E[−floor(goals)/2] from Poisson(λ opp), "
            "split among defenders by minutes_w.",
        )
    else:
        _ln("Goals conceded", gc, "not applied to MID/FWD in this model.")

    _ln(
        "Saves",
        float(bd["saves"]),
        "not modelled (no saves on Element in silver) → 0.",
    )
    _ln(
        "Def. contributions",
        float(bd["defensive_contrib"]),
        "2025/26 DC rule: linear proxy from defensive_contribution_per_90 "
        "(official static) × minutes_w, capped at 2 (see fpl_scoring_2526).",
    )
    _ln("Cards", float(bd["cards"]), "not modelled → 0.")
    _ln(
        "Bonus (BPS)",
        float(bd["bonus"]),
        "season bonus total / minutes → per-90 rate × minutes_w, cap 3/GW.",
    )

    parts = (
        float(bd["appearance"])
        + float(bd["goals"])
        + float(bd["assists"])
        + float(bd["clean_sheet"])
        + float(bd["goals_conceded"])
        + float(bd["saves"])
        + float(bd["defensive_contrib"])
        + float(bd["cards"])
        + float(bd["bonus"])
    )
    tl = float(bd["team_lambda"])
    ol = float(bd["opp_lambda"])
    mw = float(bd["minutes_w"])
    gs = float(bd["goal_share"])
    ash = float(bd["assist_share"])
    lines += [
        "",
        "— Model numbers behind the buckets —",
        f"  position:               {pos}",
        f"  team λ (your side):     {tl:.4f}",
        f"  opp λ:                  {ol:.4f}",
        f"  minutes_w:              {mw:.4f}",
        f"  goal_share:             {gs:.4f}",
        f"  assist_share:           {ash:.4f}",
        f"  assist_scale:           {asc:.4f}",
        "",
        f"Sum of buckets: {parts:.3f} (should match xP_fpl; diff "
        f"{abs(parts - float(row['xP_fpl'])):.1e}).",
    ]
    return lines


__all__ = ["run", "verbose_breakdown_lines"]

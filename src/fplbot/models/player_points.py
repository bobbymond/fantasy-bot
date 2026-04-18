"""Shared helpers for player involvement weights (used by ``fpl_expected_points``)."""

from __future__ import annotations

from typing import Any

# FPL static ``status`` codes (subset): hard outs for v1 availability — re-check
# official copy when FPL adds letters.
_HARD_UNAVAILABLE_STATUS = frozenset({"i", "s", "n", "u"})

__all__ = [
    "league_forward_scale",
    "position_short_label",
    "team_finished_fixture_counts",
    "is_hard_unavailable",
]


def is_hard_unavailable(row: dict[str, Any]) -> bool:
    """True when bootstrap ``status`` means no minutes expected this GW (v1).

    **i** injured, **s** suspended, **n** not in squad next GW, **u** unavailable
    (per FPL copy). **d** doubtful and **a** available are *not* hard-zero here;
    see TASKS Later § availability.
    """
    st = row.get("status")
    if st is None or st == "":
        return False
    return str(st).strip().lower() in _HARD_UNAVAILABLE_STATUS


def position_short_label(element_type: int) -> str:
    """FPL roster position tags for CLI (``element_type`` 1–4)."""
    return {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}.get(int(element_type), "?")


def _float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return default
    return default


def _bonus_points_per_90(row: dict[str, Any]) -> float:
    """Season FPL bonus points divided by minutes played (0 if no minutes)."""
    mins = int(row.get("minutes") or 0)
    if mins <= 0:
        return 0.0
    bonus = int(row.get("bonus") or 0)
    return 90.0 * float(bonus) / float(mins)


def team_finished_fixture_counts(fixtures: list[dict[str, Any]]) -> dict[int, int]:
    """Count **finished** silver fixtures per ``team_h`` / ``team_a`` id."""
    counts: dict[int, int] = {}
    for fx in fixtures:
        if not fx.get("finished"):
            continue
        try:
            th = int(fx["team_h"])
            ta = int(fx["team_a"])
        except (KeyError, TypeError, ValueError):
            continue
        counts[th] = counts.get(th, 0) + 1
        counts[ta] = counts.get(ta, 0) + 1
    return counts


def _defensive_actions_per_90(row: dict[str, Any]) -> float:
    """Official defensive-contribution action rate (CBIT / CBIRT), per FPL static."""
    v = row.get("defensive_contribution_per_90")
    if v is not None and v != "":
        return max(0.0, _float(v, 0.0))
    mins = int(row.get("minutes") or 0)
    if mins <= 0:
        return 0.0
    dc = float(row.get("defensive_contribution") or 0)
    return 90.0 * dc / float(mins)


def _minutes_share(
    row: dict[str, Any],
    *,
    team_completed_fixtures: int,
) -> float:
    """Rough involvement weight from season minutes vs team fixture opportunities.

    ``team_completed_fixtures`` = finished matches that team played (from silver
    ``fixtures``). Denominator ``90 × max(1, n)`` so pre-first-finish does not
    divide by zero. Still a v1 proxy — see docs/TASKS.md **Later** § minutes.
    """
    minutes = int(row.get("minutes") or 0)
    n = max(1, int(team_completed_fixtures))
    raw = float(minutes) / (90.0 * float(n))
    return max(0.08, min(1.0, raw))


def _attack_weight(row: dict[str, Any]) -> float:
    egi = _float(row.get("expected_goal_involvements"))
    if egi <= 0:
        xg = _float(row.get("expected_goals"))
        xa = _float(row.get("expected_assists"))
        egi = xg + 0.6 * xa
    if egi <= 0:
        gs = float(row.get("goals_scored") or 0)
        ast = float(row.get("assists") or 0)
        egi = gs + 0.5 * ast + 0.25
    ict = _float(row.get("ict_index"))
    return max(0.15, egi + 0.01 * ict)


def league_forward_scale(players: list[dict[str, Any]]) -> float:
    """Typical forward involvement weight (kept for other model code / tests)."""
    ws = [_attack_weight(p) for p in players if int(p.get("element_type", 0)) == 4]
    if not ws:
        return 5.0
    return max(1.0, float(sum(ws)) / len(ws))

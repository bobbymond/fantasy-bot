"""CLI backing: load silver + model params → projections for one GW."""

from __future__ import annotations

from dataclasses import asdict

from fplbot.models.pipeline import PlayerProjection, project_gw
from fplbot.settings import load_app_config

_VALID_POSITIONS = frozenset({"GK", "DEF", "MID", "FWD"})


def _normalize_position_filter(position: str | None) -> str | None:
    if position is None:
        return None
    s = str(position).strip().upper()
    if not s:
        return None
    if s not in _VALID_POSITIONS:
        choices = ", ".join(sorted(_VALID_POSITIONS))
        msg = f"invalid position {position!r}; expected one of: {choices}"
        raise ValueError(msg)
    return s


def _normalize_team_query(team: str | None) -> str | None:
    if team is None:
        return None
    s = str(team).strip()
    return s if s else None


def _row_matches_team(r: PlayerProjection, query: str | None) -> bool:
    if not query:
        return True
    if query.isdigit():
        return r.team_id == int(query)
    return r.team_short.upper() == query.upper()


def run(
    *,
    gw: int | None = None,
    top: int = 15,
    position: str | None = None,
    team: str | None = None,
) -> tuple[int, list[dict[str, object]]]:
    """Return ``(gw_id, rows)`` for printing (dicts for Typer simplicity).

    ``position`` filters to one of GK, DEF, MID, FWD (case-insensitive).
    ``team`` matches ``team_short`` (case-insensitive) or numeric ``team_id``.
    Rows stay sorted by ``xP_fpl`` descending; ``top`` caps how many are returned
    after filtering.
    """
    pos_f = _normalize_position_filter(position)
    team_q = _normalize_team_query(team)
    cfg = load_app_config()
    gw_id, rows = project_gw(cfg.paths.silver, cfg.model, gw=gw)
    filtered = [
        r
        for r in rows
        if (pos_f is None or r.position == pos_f) and _row_matches_team(r, team_q)
    ]
    slim = [asdict(r) for r in filtered[: max(1, top)]]
    return gw_id, slim


__all__ = ["run"]

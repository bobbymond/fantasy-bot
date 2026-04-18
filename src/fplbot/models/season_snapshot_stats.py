"""Aggregates on silver ``players`` rows (FPL bootstrap season-to-date fields)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

__all__ = ["LeagueGoalsAssists", "league_goals_assists_totals", "read_players_rows"]


@dataclass(frozen=True)
class LeagueGoalsAssists:
    """Sums over all elements in one ``players.parquet`` snapshot."""

    goals_scored: int
    assists: int

    @property
    def assists_per_goal(self) -> float:
        if self.goals_scored <= 0:
            return 0.0
        return float(self.assists) / float(self.goals_scored)


def league_goals_assists_totals(
    players: Iterable[dict[str, Any]],
) -> LeagueGoalsAssists:
    """Sum ``goals_scored`` and ``assists`` (FPL element season-to-date)."""
    g = a = 0
    for p in players:
        g += int(p.get("goals_scored") or 0)
        a += int(p.get("assists") or 0)
    return LeagueGoalsAssists(goals_scored=g, assists=a)


def read_players_rows(players_parquet: Path) -> list[dict[str, Any]]:
    """Load ``players.parquet`` as row dicts."""
    if not players_parquet.is_file():
        msg = f"players table missing: {players_parquet}"
        raise FileNotFoundError(msg)
    return pq.read_table(players_parquet).to_pylist()

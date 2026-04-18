"""Silver player aggregate helpers."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from fplbot.models.season_snapshot_stats import (
    league_goals_assists_totals,
    read_players_rows,
)


def test_league_goals_assists_totals_sums() -> None:
    rows = [
        {"goals_scored": 2, "assists": 1},
        {"goals_scored": 0, "assists": 3},
    ]
    t = league_goals_assists_totals(rows)
    assert t.goals_scored == 2
    assert t.assists == 4
    assert abs(t.assists_per_goal - 2.0) < 1e-9


def test_read_players_rows_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_players_rows(tmp_path / "nope.parquet")


def test_read_players_rows_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "players.parquet"
    table = pa.Table.from_pylist(
        [{"id": 1, "goals_scored": 5, "assists": 2, "team": 1}]
    )
    pq.write_table(table, p)
    rows = read_players_rows(p)
    assert league_goals_assists_totals(rows).goals_scored == 5

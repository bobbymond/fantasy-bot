"""Load silver Parquet + metadata; resolve target gameweek."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

__all__ = ["SilverSnapshot", "load_silver", "resolve_target_gw"]


@dataclass(frozen=True)
class SilverSnapshot:
    """In-memory silver tables as row dicts (small enough for CLI / tests)."""

    metadata: dict[str, Any]
    events: list[dict[str, Any]]
    teams: list[dict[str, Any]]
    players: list[dict[str, Any]]
    fixtures: list[dict[str, Any]]


def load_silver(silver_dir: Path) -> SilverSnapshot:
    """Read events/teams/players/fixtures Parquet plus ``metadata.json``."""
    meta_path = silver_dir / "metadata.json"
    if not meta_path.is_file():
        msg = f"silver metadata missing: {meta_path}"
        raise FileNotFoundError(msg)
    meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))

    def _rows(name: str) -> list[dict[str, Any]]:
        path = silver_dir / name
        if not path.is_file():
            msg = f"silver table missing: {path}"
            raise FileNotFoundError(msg)
        return pq.read_table(path).to_pylist()

    return SilverSnapshot(
        metadata=meta,
        events=_rows("events.parquet"),
        teams=_rows("teams.parquet"),
        players=_rows("players.parquet"),
        fixtures=_rows("fixtures.parquet"),
    )


def resolve_target_gw(
    events: list[dict[str, Any]],
    *,
    gw_override: int | None,
) -> int:
    """Default: FPL ``is_next`` event; else first unfinished; else max id."""
    if gw_override is not None:
        return int(gw_override)
    for e in events:
        if e.get("is_next"):
            return int(e["id"])
    unfinished = [int(e["id"]) for e in events if not e.get("finished", False)]
    if unfinished:
        return min(unfinished)
    return max(int(e["id"]) for e in events)

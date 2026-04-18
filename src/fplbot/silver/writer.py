"""Write normalised silver tables as Parquet + sidecar metadata."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from fplbot.ingest.models import Bootstrap, Fixture

SILVER_SCHEMA_VERSION = 4

__all__ = ["SILVER_SCHEMA_VERSION", "write_silver"]


def write_silver(
    silver_dir: Path,
    bootstrap: Bootstrap,
    fixtures: list[Fixture],
    *,
    fpl_cache_run_id: str,
    ingested_at: str | None = None,
) -> None:
    """Overwrite ``players.parquet``, ``teams.parquet``, ``fixtures.parquet``,
    ``events.parquet``, and ``metadata.json`` under ``silver_dir``.
    """
    silver_dir.mkdir(parents=True, exist_ok=True)
    stamp = ingested_at or datetime.now(UTC).replace(microsecond=0).isoformat()

    events_rows = [e.model_dump() for e in bootstrap.events]
    teams_rows = [t.model_dump() for t in bootstrap.teams]
    players_rows = [p.model_dump() for p in bootstrap.elements]
    fixtures_rows = [f.model_dump() for f in fixtures]
    _write_parquet(silver_dir / "events.parquet", events_rows)
    _write_parquet(silver_dir / "teams.parquet", teams_rows)
    _write_parquet(silver_dir / "players.parquet", players_rows)
    _write_parquet(silver_dir / "fixtures.parquet", fixtures_rows)

    meta: dict[str, Any] = {
        "silver_schema_version": SILVER_SCHEMA_VERSION,
        "ingested_at": stamp,
        "fpl_cache_run_id": fpl_cache_run_id,
    }
    (silver_dir / "metadata.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)

"""Write normalised silver tables as Parquet + sidecar metadata."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from fplbot.ingest.models import Bootstrap, Fixture
from fplbot.ingest.prior_season import SeasonPrior

SILVER_SCHEMA_VERSION = 5

__all__ = ["SILVER_SCHEMA_VERSION", "write_silver", "write_season_priors"]


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


def write_season_priors(
    silver_dir: Path,
    priors: list[SeasonPrior],
    *,
    season: int,
    ingested_at: str | None = None,
) -> None:
    """Write season priors to Parquet file."""
    silver_dir.mkdir(parents=True, exist_ok=True)
    stamp = ingested_at or datetime.now(UTC).replace(microsecond=0).isoformat()

    priors_rows = [
        {
            "season": prior.season,
            "team_id": prior.team_id,
            "team_name": prior.team_name,
            "home_attack": prior.home_attack,
            "away_attack": prior.away_attack,
            "home_defence": prior.home_defence,
            "away_defence": prior.away_defence,
            "matches_played": prior.matches_played,
        }
        for prior in priors
    ]
    
    _write_parquet(silver_dir / "season_priors.parquet", priors_rows)
    
    # Update metadata to include season priors info
    meta_path = silver_dir / "metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta = {}
    
    meta.update({
        "season_priors_season": season,
        "season_priors_ingested_at": stamp,
        "season_priors_count": len(priors),
    })
    
    meta_path.write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)

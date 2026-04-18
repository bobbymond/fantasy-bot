"""Official FPL JSON → versioned cache under ``cache/fpl/`` + Parquet silver."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from fplbot.ingest.client import FplClient
from fplbot.ingest.errors import FplIngestError
from fplbot.ingest.models import parse_bootstrap, parse_fixtures
from fplbot.settings import load_paths
from fplbot.silver.writer import write_silver


@dataclass(frozen=True)
class FplIngestSummary:
    """What ``run()`` wrote — useful for CLI output and tests."""

    run_id: str
    ingested_at: str
    run_dir: Path
    manifest_path: Path
    silver_dir: Path
    n_events: int
    n_teams: int
    n_players: int
    n_fixtures: int


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json_pretty(path: Path, obj: Any) -> None:
    text = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _write_manifest(fpl_cache: Path, payload: dict[str, Any]) -> None:
    fpl_cache.mkdir(parents=True, exist_ok=True)
    target = fpl_cache / "manifest.json"
    tmp = fpl_cache / "manifest.json.tmp"
    manifest_body = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    tmp.write_text(manifest_body, encoding="utf-8")
    tmp.replace(target)


def run(*, http_client: httpx.Client | None = None) -> FplIngestSummary:
    """Fetch bootstrap + fixtures, write a versioned cache run, refresh silver."""
    paths = load_paths()
    paths.fpl_cache.mkdir(parents=True, exist_ok=True)
    paths.silver.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = paths.fpl_cache / run_id
    run_dir.mkdir(parents=False)

    try:
        with FplClient(http_client) as api:
            bootstrap_obj = api.fetch_bootstrap_dict()
            fixtures_obj = api.fetch_fixtures_list()
    except ValidationError as exc:  # pragma: no cover - client returns JSON first
        raise FplIngestError(f"Unexpected validation error on fetch: {exc}") from exc

    _write_json_pretty(run_dir / "bootstrap.json", bootstrap_obj)
    _write_json_pretty(run_dir / "fixtures.json", fixtures_obj)

    bootstrap_hash = _sha256_hex(_canonical_json_bytes(bootstrap_obj))
    fixtures_hash = _sha256_hex(_canonical_json_bytes(fixtures_obj))

    ingested_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    manifest: dict[str, Any] = {
        "ingested_at": ingested_at,
        "run_id": run_id,
        "bootstrap": {
            "path": str(run_dir / "bootstrap.json"),
            "sha256": bootstrap_hash,
        },
        "fixtures": {
            "path": str(run_dir / "fixtures.json"),
            "sha256": fixtures_hash,
        },
    }
    _write_manifest(paths.fpl_cache, manifest)

    try:
        bootstrap = parse_bootstrap(bootstrap_obj)
        fixtures = parse_fixtures(fixtures_obj)
    except ValidationError as exc:
        raise FplIngestError(f"FPL JSON failed validation: {exc}") from exc

    write_silver(
        paths.silver,
        bootstrap,
        fixtures,
        fpl_cache_run_id=run_id,
        ingested_at=ingested_at,
    )

    return FplIngestSummary(
        run_id=run_id,
        ingested_at=ingested_at,
        run_dir=run_dir,
        manifest_path=paths.fpl_cache / "manifest.json",
        silver_dir=paths.silver,
        n_events=len(bootstrap.events),
        n_teams=len(bootstrap.teams),
        n_players=len(bootstrap.elements),
        n_fixtures=len(fixtures),
    )


__all__ = ["FplIngestSummary", "run"]

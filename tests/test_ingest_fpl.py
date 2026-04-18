"""FPL ingest with HTTP mocked (``respx`` + checked-in JSON)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
import respx

from fplbot.ingest import fpl as fpl_ingest
from fplbot.ingest.client import BOOTSTRAP_URL, FIXTURES_URL
from fplbot.silver.writer import SILVER_SCHEMA_VERSION


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "fpl" / name


def _load_json(name: str) -> object:
    text = _fixture_path(name).read_text(encoding="utf-8")
    return json.loads(text)


@pytest.fixture
def project_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Use a temp cwd so ingest writes under tmp/cache and tmp/data."""
    (tmp_path / "cache" / "fpl").mkdir(parents=True)
    (tmp_path / "data" / "silver").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@respx.mock
def test_ingest_fpl_writes_cache_manifest_and_silver(project_tmp: Path) -> None:
    bootstrap = _load_json("min_bootstrap.json")
    fixtures = _load_json("min_fixtures.json")

    respx.get(BOOTSTRAP_URL).mock(return_value=httpx.Response(200, json=bootstrap))
    respx.get(FIXTURES_URL).mock(return_value=httpx.Response(200, json=fixtures))

    summary = fpl_ingest.run()
    assert summary.n_players == 3
    assert summary.n_fixtures == 3

    fpl_cache = project_tmp / "cache" / "fpl"
    manifest = json.loads((fpl_cache / "manifest.json").read_text(encoding="utf-8"))
    run_id = manifest["run_id"]
    assert summary.run_id == run_id
    assert manifest["bootstrap"]["sha256"]
    assert manifest["fixtures"]["sha256"]
    assert (fpl_cache / run_id / "bootstrap.json").is_file()
    assert (fpl_cache / run_id / "fixtures.json").is_file()

    silver = project_tmp / "data" / "silver"
    meta = json.loads((silver / "metadata.json").read_text(encoding="utf-8"))
    assert meta["silver_schema_version"] == SILVER_SCHEMA_VERSION
    assert meta["fpl_cache_run_id"] == run_id

    assert (silver / "events.parquet").is_file()
    assert (silver / "teams.parquet").is_file()
    assert (silver / "players.parquet").is_file()
    assert (silver / "fixtures.parquet").is_file()


@respx.mock
def test_ingest_fpl_row_counts(project_tmp: Path) -> None:
    bootstrap = _load_json("min_bootstrap.json")
    fixtures = _load_json("min_fixtures.json")
    respx.get(BOOTSTRAP_URL).mock(return_value=httpx.Response(200, json=bootstrap))
    respx.get(FIXTURES_URL).mock(return_value=httpx.Response(200, json=fixtures))

    fpl_ingest.run()

    silver = project_tmp / "data" / "silver"
    assert pq.read_table(silver / "events.parquet").num_rows == 3
    assert pq.read_table(silver / "teams.parquet").num_rows == 2
    assert pq.read_table(silver / "players.parquet").num_rows == 3
    assert pq.read_table(silver / "fixtures.parquet").num_rows == 3

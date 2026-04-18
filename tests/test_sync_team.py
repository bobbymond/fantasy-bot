"""``sync-team`` / ``ingest.team_snapshot`` with mocked HTTP."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import pytest
import respx

from fplbot.ingest import team_snapshot as ts
from fplbot.ingest.errors import TeamSnapshotError
from fplbot.settings import load_app_config
from fplbot.team_state import FileTeamStateSource
from fplbot.team_state.snapshot_schema import MY_TEAM_SCHEMA_VERSION


def _picks(n: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for i in range(1, n + 1):
        rows.append(
            {
                "element": 250 + i,
                "position": i,
                "selling_price": 50,
                "purchase_price": 50,
                "multiplier": 2 if i == 1 else 1,
                "is_captain": i == 1,
                "is_vice_captain": i == 2,
            }
        )
    return rows


@pytest.fixture
def sync_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[Path, int]:
    """Temp cwd + config with ``fpl.entry_id``."""
    eid = 424242
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "\n".join(
            [
                "paths:",
                "  my_team: squad.json",
                "fpl:",
                f"  entry_id: {eid}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FPL_SESSION_COOKIE", "session=dummy")
    return tmp_path, eid


@respx.mock
def test_sync_team_writes_normalised_snapshot(sync_project: tuple[Path, int]) -> None:
    tmp, eid = sync_project
    entry = {
        "id": eid,
        "name": "Test United",
        "current_event": 7,
        "last_deadline_bank": 42,
        "last_deadline_value": 1000,
        "last_deadline_total_transfers": 2,
    }
    my_team = {
        "picks": _picks(15),
        "transfers": {"limit": 1, "bank": 42, "value": 1000},
        "active_chip": None,
    }
    transfers: list[object] = [{"id": 1, "element_in": 1, "element_out": 2}]

    respx.get(ts.ENTRY_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=entry)
    )
    respx.get(ts.MY_TEAM_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=my_team)
    )
    respx.get(ts.TRANSFERS_LATEST_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=transfers)
    )

    summary = ts.run()
    assert summary.entry_id == eid
    assert summary.n_picks == 15
    assert summary.transfer_history_rows == 1

    out_path = tmp / "squad.json"
    assert summary.path == out_path.resolve()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == MY_TEAM_SCHEMA_VERSION
    assert data["entry_id"] == eid
    assert data["entry"]["name"] == "Test United"
    assert len(data["picks"]) == 15
    assert data["picks"][0]["element_id"] == 251
    assert data["picks"][0]["is_captain"] is True

    src = FileTeamStateSource(out_path)
    assert src.load_my_team_dict()["schema_version"] == MY_TEAM_SCHEMA_VERSION


@respx.mock
def test_sync_team_default_path_is_cache_my_team_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default ``paths.my_team`` is ``cache/my_team.json``; parent dir is created."""
    eid = 7
    (tmp_path / "config.yaml").write_text(
        f"fpl:\n  entry_id: {eid}\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FPL_SESSION_COOKIE", "session=dummy")
    entry = {
        "id": eid,
        "name": "Def",
        "current_event": 1,
        "last_deadline_bank": 0,
        "last_deadline_value": 1000,
        "last_deadline_total_transfers": 0,
    }
    my_team = {"picks": _picks(15), "transfers": {}, "active_chip": None}
    respx.get(ts.ENTRY_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=entry)
    )
    respx.get(ts.MY_TEAM_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=my_team)
    )
    respx.get(ts.TRANSFERS_LATEST_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=[])
    )
    assert not (tmp_path / "cache").exists()
    summary = ts.run()
    out = tmp_path / "cache" / "my_team.json"
    assert summary.path == out.resolve()
    assert out.is_file()


def test_sync_team_requires_cookie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config.yaml").write_text(
        "fpl:\n  entry_id: 1\npaths:\n  my_team: m.json\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FPL_SESSION_COOKIE", raising=False)
    with pytest.raises(TeamSnapshotError, match="FPL_SESSION_COOKIE"):
        ts.run()


def test_sync_team_requires_entry_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FPL_SESSION_COOKIE", "x=1")
    (tmp_path / "config.yaml").write_text("fpl:\n  entry_id: null\n", encoding="utf-8")
    with pytest.raises(TeamSnapshotError, match="entry id"):
        ts.run()


def test_load_app_config_entry_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "fpl:\n  entry_id: 99\npaths:\n  my_team: x.json\n",
        encoding="utf-8",
    )
    cfg = load_app_config()
    assert cfg.fpl_entry_id == 99
    assert cfg.paths.my_team == (tmp_path / "x.json").resolve()
    assert cfg.model.strength_window_gw == 0


@respx.mock
def test_entry_id_override_wins_over_config(
    sync_project: tuple[Path, int],
) -> None:
    """``entry_id_override`` wins over config (unit-level on ``run``)."""
    tmp, _cfg_eid = sync_project
    override = 999001
    entry = {"id": override, "name": "O", "current_event": 1}
    my_team = {"picks": _picks(2), "transfers": {}}

    respx.get(ts.ENTRY_URL.format(entry_id=override)).mock(
        return_value=httpx.Response(200, json=entry)
    )
    respx.get(ts.MY_TEAM_URL.format(entry_id=override)).mock(
        return_value=httpx.Response(200, json=my_team)
    )
    respx.get(ts.TRANSFERS_LATEST_URL.format(entry_id=override)).mock(
        return_value=httpx.Response(200, json=[])
    )
    summary = ts.run(entry_id_override=override)

    assert summary.entry_id == override
    data = json.loads((tmp / "squad.json").read_text(encoding="utf-8"))
    assert data["entry_id"] == override
    assert len(data["picks"]) == 2


@respx.mock
def test_sync_team_log_requests_redacts_cookie(
    caplog: pytest.LogCaptureFixture,
    sync_project: tuple[Path, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, eid = sync_project
    monkeypatch.setenv("FPL_X_API_AUTHORIZATION", "secret-x-api-token")
    entry = {
        "id": eid,
        "name": "Test United",
        "current_event": 7,
        "last_deadline_bank": 42,
        "last_deadline_value": 1000,
        "last_deadline_total_transfers": 2,
    }
    my_team = {
        "picks": _picks(15),
        "transfers": {"limit": 1, "bank": 42, "value": 1000},
        "active_chip": None,
    }
    respx.get(ts.ENTRY_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=entry)
    )
    respx.get(ts.MY_TEAM_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=my_team)
    )
    respx.get(ts.TRANSFERS_LATEST_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=[])
    )
    with caplog.at_level(logging.INFO, logger="fplbot.ingest.team_snapshot"):
        ts.run(log_requests=True)
    text = caplog.text
    assert "HTTP GET" in text
    assert "<redacted" in text
    assert "session=dummy" not in text
    assert "secret-x-api-token" not in text


@respx.mock
def test_sync_team_sends_x_api_authorization_header(
    sync_project: tuple[Path, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``FPL_X_API_AUTHORIZATION`` is sent as ``X-Api-Authorization`` on API calls."""
    tmp, eid = sync_project
    monkeypatch.setenv("FPL_X_API_AUTHORIZATION", "test-jwt-sig")
    entry = {
        "id": eid,
        "name": "T",
        "current_event": 1,
        "last_deadline_bank": 0,
        "last_deadline_value": 1000,
        "last_deadline_total_transfers": 0,
    }
    my_team = {"picks": _picks(15), "transfers": {}, "active_chip": None}
    respx.get(ts.ENTRY_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=entry)
    )
    my_route = respx.get(ts.MY_TEAM_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=my_team)
    )
    respx.get(ts.TRANSFERS_LATEST_URL.format(entry_id=eid)).mock(
        return_value=httpx.Response(200, json=[])
    )
    summary = ts.run()
    req = my_route.calls.last.request
    lowered = {k.lower(): v for k, v in req.headers.items()}
    assert lowered.get("x-api-authorization") == "test-jwt-sig"
    assert summary.path == (tmp / "squad.json").resolve()

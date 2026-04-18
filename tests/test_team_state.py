"""Phase 2 scaffold: paths + ``TeamStateSource``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fplbot.settings import load_paths
from fplbot.team_state import FileTeamStateSource
from fplbot.team_state.protocol import read_my_team_json


def test_paths_my_team_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    p = load_paths()
    assert p.my_team == tmp_path / "cache" / "my_team.json"


def test_file_team_state_source_missing(tmp_path: Path) -> None:
    src = FileTeamStateSource(tmp_path / "nope.json")
    with pytest.raises(FileNotFoundError, match="sync-team"):
        src.load_my_team_dict()


def test_read_my_team_json_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "my_team.json"
    path.write_text(json.dumps({"ok": True, "picks": []}), encoding="utf-8")
    assert read_my_team_json(path)["ok"] is True

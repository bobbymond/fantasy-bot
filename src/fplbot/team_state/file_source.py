"""``TeamStateSource`` backed by ``my_team.json`` on disk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fplbot.team_state.protocol import read_my_team_json


class FileTeamStateSource:
    """Load squad snapshot written by ``sync-team``."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def load_my_team_dict(self) -> dict[str, Any]:
        if not self._path.is_file():
            raise FileNotFoundError(
                f"my_team snapshot missing: {self._path} — run `fplbot sync-team` "
                "after Phase 2 is implemented"
            )
        return read_my_team_json(self._path)


__all__ = ["FileTeamStateSource"]

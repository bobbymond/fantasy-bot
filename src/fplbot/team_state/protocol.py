"""Provider interface for current squad snapshot (no HTTP)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TeamStateSource(Protocol):
    """Reads a normalised ``my_team`` snapshot produced by ``sync-team``."""

    @property
    def path(self) -> Path:
        """Filesystem path to the JSON file."""
        ...

    def load_my_team_dict(self) -> dict[str, Any]:
        """Return parsed JSON (shape validated further in later phases)."""
        ...


def read_my_team_json(path: Path) -> dict[str, Any]:
    """Shared helper: load UTF-8 JSON object from ``path``."""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"my_team file must contain a JSON object: {path}")
    return data


__all__ = ["TeamStateSource", "read_my_team_json"]

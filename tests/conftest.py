"""Pytest hooks: keep live HTTP tests out of the default collection."""

from __future__ import annotations

import os
from pathlib import Path


def _live_fpl_enabled() -> bool:
    v = os.environ.get("RUN_LIVE_FPL", "").lower().strip()
    return v in ("1", "true", "yes", "on")


def pytest_ignore_collect(collection_path: Path) -> bool | None:
    """Skip ``tests/contract/`` unless ``RUN_LIVE_FPL`` is set (truthy)."""
    parts = collection_path.parts
    if len(parts) >= 2 and parts[-2] == "contract" and collection_path.suffix == ".py":
        return not _live_fpl_enabled()
    return None

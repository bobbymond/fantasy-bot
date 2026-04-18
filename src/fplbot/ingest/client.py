"""HTTP client for public FPL JSON endpoints."""

from __future__ import annotations

from typing import Any

import httpx

from fplbot.ingest.errors import FplIngestError

BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"
USER_AGENT = "fplbot/0.1.0 (local advisory tool)"

__all__ = ["BOOTSTRAP_URL", "FIXTURES_URL", "FplClient"]


class FplClient:
    """Thin wrapper around ``httpx`` for bootstrap + fixtures."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
        self._own_client = client is None

    def close(self) -> None:
        if self._own_client:
            self._client.close()

    def __enter__(self) -> FplClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def fetch_bootstrap_dict(self) -> dict[str, Any]:
        resp = self._client.get(BOOTSTRAP_URL)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise FplIngestError("bootstrap-static: top-level JSON must be an object")
        return data

    def fetch_fixtures_list(self) -> list[Any]:
        resp = self._client.get(FIXTURES_URL)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise FplIngestError("fixtures: top-level JSON must be an array")
        return data

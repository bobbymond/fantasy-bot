"""Authenticated FPL Classic snapshot → ``my_team.json`` (Phase 2).

**Only this module** should attach session cookies for FPL Classic.
Downstream code uses :class:`fplbot.team_state.FileTeamStateSource` to read the file.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from fplbot.ingest.client import USER_AGENT
from fplbot.ingest.errors import TeamSnapshotError
from fplbot.ingest.team_snapshot_models import ApiMyTeamPayload
from fplbot.settings import AppConfig, Paths, load_app_config
from fplbot.team_state.snapshot_schema import (
    MY_TEAM_SCHEMA_VERSION,
    EntrySummary,
    MyTeamSnapshotV1,
    PickNorm,
)

FPL_ORIGIN = "https://fantasy.premierleague.com"

# Optional; some FPL API calls send this in addition to ``Cookie`` (see DevTools).
X_API_AUTHORIZATION_HEADER = "X-Api-Authorization"
FPL_X_API_AUTHORIZATION_ENV = "FPL_X_API_AUTHORIZATION"

ENTRY_URL = "https://fantasy.premierleague.com/api/entry/{entry_id}/"
MY_TEAM_URL = "https://fantasy.premierleague.com/api/my-team/{entry_id}/"
TRANSFERS_LATEST_URL = (
    "https://fantasy.premierleague.com/api/entry/{entry_id}/transfers-latest/"
)

logger = logging.getLogger(__name__)

_MY_TEAM_AUTH_HINT = (
    "/api/entry/ is often public — a 200 there does not prove your session works. "
    "/api/my-team/ needs a Cookie that already works for that URL in your browser "
    "(same DevTools row as a 200 for my-team or picks). --entry-id must match "
    "that login. If DevTools shows X-Api-Authorization, set env "
    f"{FPL_X_API_AUTHORIZATION_ENV} (see README). "
    "With --verbose, a truncated 403 response body is logged if present."
)


@dataclass(frozen=True)
class TeamSyncSummary:
    """What ``run()`` wrote — for CLI output."""

    entry_id: int
    path: Path
    n_picks: int
    fetched_at: str
    transfer_history_rows: int


def _headers_for_log(headers: httpx.Headers) -> dict[str, str]:
    """Copy headers for logging; never emit raw Cookie or *Authorization* values."""
    out: dict[str, str] = {}
    for key, value in headers.items():
        lk = key.lower()
        if lk == "cookie" or "authorization" in lk:
            out[key] = f"<redacted {len(value)} chars>"
        else:
            out[key] = value
    return out


def _log_request(request: httpx.Request) -> None:
    logger.info("HTTP %s %s", request.method, request.url)
    logger.info("request headers: %s", _headers_for_log(request.headers))


def _make_response_logger(
    *, log_error_bodies: bool
) -> Callable[[httpx.Response], None]:
    def log_response(response: httpx.Response) -> None:
        req = response.request
        logger.info("HTTP %s %s <- %s", req.method, req.url, response.status_code)
        if not log_error_bodies or response.status_code < 400:
            return
        raw = (response.text or "")[:1200]
        snippet = " ".join(raw.split())
        if snippet:
            logger.info("response body (truncated): %s", snippet)

    return log_response


def _session_client(cookie: str, *, log_requests: bool = False) -> httpx.Client:
    """Same-origin JSON fetches; ``Sec-Fetch-*`` mimics a browser XHR."""
    ua = os.environ.get("FPLBOT_SYNC_USER_AGENT", "").strip() or USER_AGENT
    hdrs: dict[str, str] = {
        "User-Agent": ua,
        "Cookie": cookie.strip(),
        "Accept": "application/json",
        "Accept-Language": "en-GB,en;q=0.9",
        "Referer": f"{FPL_ORIGIN}/",
        "Origin": FPL_ORIGIN,
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }
    x_api = os.environ.get(FPL_X_API_AUTHORIZATION_ENV, "").strip()
    if x_api:
        hdrs[X_API_AUTHORIZATION_HEADER] = x_api
    kwargs: dict[str, Any] = {
        "headers": hdrs,
        "timeout": httpx.Timeout(30.0),
        "follow_redirects": True,
    }
    if log_requests:
        kwargs["event_hooks"] = {
            "request": [_log_request],
            "response": [_make_response_logger(log_error_bodies=True)],
        }
    return httpx.Client(**kwargs)


def _get_json(
    client: httpx.Client, url: str, *, auth_failure_extra: str | None = None
) -> Any:
    resp = client.get(url)
    if resp.status_code in (401, 403):
        msg = (
            f"FPL returned HTTP {resp.status_code} for {url} — "
            "check FPL_SESSION_COOKIE (expired or wrong entry id)."
        )
        if auth_failure_extra:
            msg = f"{msg}\n{auth_failure_extra}"
        raise TeamSnapshotError(msg)
    resp.raise_for_status()
    return resp.json()


def _get_json_optional(client: httpx.Client, url: str) -> Any:
    """Return JSON or empty list on auth failure (transfers-latest edge cases)."""
    resp = client.get(url)
    if resp.status_code in (401, 403):
        return []
    resp.raise_for_status()
    return resp.json()


def _build_snapshot(
    *,
    entry_id: int,
    entry_raw: dict[str, Any],
    my_team: ApiMyTeamPayload,
    transfer_history: list[Any],
    fetched_at: str,
) -> MyTeamSnapshotV1:
    entry_summary = EntrySummary.model_validate(
        {
            "name": entry_raw.get("name"),
            "last_deadline_bank": entry_raw.get("last_deadline_bank"),
            "last_deadline_value": entry_raw.get("last_deadline_value"),
            "last_deadline_total_transfers": entry_raw.get(
                "last_deadline_total_transfers"
            ),
        }
    )
    picks_norm = [
        PickNorm(
            element_id=p.element,
            squad_slot=p.position,
            multiplier=p.multiplier,
            is_captain=p.is_captain,
            is_vice_captain=p.is_vice_captain,
            selling_price=p.selling_price,
            purchase_price=p.purchase_price,
        )
        for p in my_team.picks
    ]
    transfers_state: dict[str, Any] = dict(my_team.transfers or {})
    return MyTeamSnapshotV1(
        schema_version=MY_TEAM_SCHEMA_VERSION,
        fetched_at=fetched_at,
        entry_id=entry_id,
        current_event=entry_raw.get("current_event")
        if isinstance(entry_raw.get("current_event"), int)
        else None,
        entry=entry_summary,
        transfers_state=transfers_state,
        picks=picks_norm,
        transfer_history=transfer_history if isinstance(transfer_history, list) else [],
        active_chip=my_team.active_chip,
    )


def run(
    *,
    entry_id_override: int | None = None,
    paths: Paths | None = None,
    config: AppConfig | None = None,
    http_client: httpx.Client | None = None,
    log_requests: bool | None = None,
) -> TeamSyncSummary:
    """Fetch entry + my-team (+ transfers-latest), write normalised ``my_team.json``.

    When ``log_requests`` is true (or env ``FPLBOT_LOG_HTTP`` is truthy), log each
    outgoing request and response status to the ``fplbot.ingest.team_snapshot``
    logger — **Cookie** and **Authorization** values are never logged verbatim.
    """
    cfg = config or load_app_config()
    paths = paths or cfg.paths
    entry_id = entry_id_override if entry_id_override is not None else cfg.fpl_entry_id
    if entry_id is None:
        raise TeamSnapshotError(
            "No entry id: set ``fpl.entry_id`` in config.yaml or pass ``--entry-id``."
        )

    if log_requests is None:
        log_requests = os.environ.get("FPLBOT_LOG_HTTP", "").lower() in (
            "1",
            "true",
            "yes",
        )

    own_client = http_client is None
    if http_client is None:
        cookie = os.environ.get("FPL_SESSION_COOKIE", "").strip()
        if not cookie:
            raise TeamSnapshotError(
                "FPL_SESSION_COOKIE is not set. Add it to repo-root .env or export it "
                "(see README, Authenticated sync-team)."
            )
        client = _session_client(cookie, log_requests=log_requests)
    else:
        client = http_client

    fetched_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    try:
        entry_url = ENTRY_URL.format(entry_id=entry_id)
        my_url = MY_TEAM_URL.format(entry_id=entry_id)
        tr_url = TRANSFERS_LATEST_URL.format(entry_id=entry_id)

        entry_raw = _get_json(client, entry_url)
        if not isinstance(entry_raw, dict):
            raise TeamSnapshotError("entry endpoint: expected a JSON object")

        my_raw = _get_json(client, my_url, auth_failure_extra=_MY_TEAM_AUTH_HINT)
        if not isinstance(my_raw, dict):
            raise TeamSnapshotError("my-team endpoint: expected a JSON object")
        try:
            my_team = ApiMyTeamPayload.model_validate(my_raw)
        except ValidationError as exc:
            raise TeamSnapshotError(f"my-team payload invalid: {exc}") from exc

        tr_raw = _get_json_optional(client, tr_url)
        transfer_history: list[Any] = tr_raw if isinstance(tr_raw, list) else []

        snapshot = _build_snapshot(
            entry_id=entry_id,
            entry_raw=entry_raw,
            my_team=my_team,
            transfer_history=transfer_history,
            fetched_at=fetched_at,
        )
        out = snapshot.model_dump(mode="json")
        paths.my_team.parent.mkdir(parents=True, exist_ok=True)
        paths.my_team.write_text(
            json.dumps(out, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return TeamSyncSummary(
            entry_id=entry_id,
            path=paths.my_team,
            n_picks=len(snapshot.picks),
            fetched_at=fetched_at,
            transfer_history_rows=len(transfer_history),
        )
    finally:
        if own_client:
            client.close()


__all__ = ["TeamSyncSummary", "run"]

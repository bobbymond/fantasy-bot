# `sync-team` — authenticated snapshot (Phase 2)

`fplbot sync-team` will be the **only** command that sends your **browser session** to Fantasy Premier League. Everything else should work from **cached** data.

## What gets written

- **Squad snapshot** (filename is conventionally `my_team.json`; path from `config.yaml` → **`paths.my_team`**, default **`cache/my_team.json`** next to the repo root) — normalised JSON: **15 picks**, **bank**, **free transfers** / hits, and whatever else downstream needs.
- **Never** commit this file or any file containing **cookies**, **tokens**, or **passwords**.

## Decisions (locked for implementation)

| Topic | Choice |
|--------|--------|
| Secret transport | **`FPL_SESSION_COOKIE`** (full **`Cookie`** value after `Cookie: `). Optional **`FPLBOT_SYNC_USER_AGENT`** and **`FPL_X_API_AUTHORIZATION`** when DevTools shows them on the same request as **`my-team`**. |
| Storing secrets locally | Manual **`.env`** at repo root — see **[README.md](../README.md#authenticated-sync-team-env)** for a template and DevTools copy steps. |
| Loading `.env` for CLI | **`fplbot sync-team`** calls **`load_dotenv()`** before work so `./.env` is picked up automatically (does not override env vars already set in your shell). |
| Entry id | **`fpl.entry_id`** in `config.yaml`; **`fplbot sync-team --entry-id N`** overrides that value for a single run. |
| `my_team.json` | **Owned normalised JSON** with a **schema version** field — not only a raw API dump. |
| Usage | **Manual** `sync-team` only — no background daemon or rapid polling. |

## Authentication (implementation notes)

`ingest.team_snapshot` uses **`httpx`** with **`Cookie`**, optional **`X-Api-Authorization`** from **`FPL_X_API_AUTHORIZATION`**, **`Accept`**, **`Accept-Language`**, **`Referer`**, **`Origin`**, and **`Sec-Fetch-*`** on `fantasy.premierleague.com`. Optional **`FPLBOT_SYNC_USER_AGENT`** overrides the default **`User-Agent`**. **`fplbot sync-team`** calls **`load_dotenv()`** so repo-local **`.env`** is loaded.

**Implemented:** `GET /api/entry/{id}/`, `GET /api/my-team/{id}/`, and `GET /api/entry/{id}/transfers-latest/` (last one may yield an empty history if FPL returns 401/403). Output is **normalised** JSON (`schema_version: 1`) — see `team_state/snapshot_schema.py`.

### HTTP 403 on `/api/my-team/`

`/api/entry/` is often **public**; **`/api/my-team/`** is not. A **403** usually means the **`Cookie` does not authorise that URL** (wrong row in Network, truncated copy, expired SSO) or **`--entry-id` is not your team** for that session. Copy **`Cookie`** from the same DevTools row where **`my-team`** or **`picks`** returns **200** in the browser. **`FPLBOT_SYNC_USER_AGENT`** can still matter for some edges; if it still 403s with a real browser UA, **`--verbose`** logs a **truncated 403 response body** (e.g. HTML from an edge) above the error line.

Typical flow:

1. Create or edit **`.env`** at the repo root (see **[README.md](../README.md#authenticated-sync-team-env)**). **`export …`** in the shell works too and overrides `.env`.
2. Set **`fpl.entry_id`** in **`config.yaml`** (or pass **`--entry-id`**).
3. From repo root: **`fplbot sync-team`** (loads **`.env`** via **`load_dotenv()`** first). Use **`--verbose`** / **`-v`** (or **`FPLBOT_LOG_HTTP=1`**) to log each request URL, headers with **Cookie** redacted, and response status.

DevTools “copy cookie” screenshots can still be added here as polish.

## Compliance

Re-read **FPL terms of use** before automating authenticated calls. Prefer **low frequency** (manual `sync-team` after you change the side), not a tight loop.

## Code map (scaffold)

| Piece | Role |
|--------|------|
| `fplbot.ingest.team_snapshot` | HTTP + secrets; writes `my_team.json` |
| `fplbot.team_state` | **`TeamStateSource`** + **`FileTeamStateSource`** for readers (no HTTP) |
| `fplbot sync-team` | CLI entry |

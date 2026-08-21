# Agent / contributor notes

Local **Fantasy Premier League (UK)** tooling — **advisory only** (nothing auto-submits picks). Canonical product decisions live in **`docs/FPL_BOT_PLAN.md`**; granular backlog in **`docs/TASKS.md`**.

---

## Stack

- **Python ≥ 3.12** (`pyproject.toml`), **`typer`** CLI entrypoint **`fplbot`** (`src/fplbot/cli/main.py`).
- **HTTP:** `httpx` for official FPL JSON and authenticated `sync-team`.
- **Silver:** `pyarrow` → Parquet under **`data/silver/`** (ignored in git except directory placeholders).
- **Numerics:** `numpy`, `scipy.stats` (Poisson, etc.).

---

## Layout (`src/fplbot/`)

| Area | Role |
|------|------|
| **`ingest/`** | `client.py`, `fpl.py` — fetch bootstrap + fixtures; **`team_snapshot.py`** — authenticated my-team flow. |
| **`silver/`** | Parquet writer + schema version bump when silver shape changes. |
| **`models/`** | Read silver only (no HTTP): **`silver_io`**, **`team_strength`** (home/away goal rates, optional `strength_window_gw`), **`match_lambda`**, **`poisson_match`**, **`fixture_scores`**, **`fpl_scoring_2526`**, **`player_points`**, **`fpl_expected_points`**, **`pipeline`** (`project_gw`, `PlayerProjection`, fixture score helpers). |
| **`team_state/`** | **`TeamStateSource`** / **`FileTeamStateSource`** — read normalised **`paths.my_team`** JSON. |
| **`commands/`** | One module per runnable command (`ingest_fpl`, `sync_team`, `model_*`, …). |
| **`cli/`** | Typer apps: **`ingest`**, **`model`**, core **`sync-team`** + future stubs. |

---

## Configuration

- **`config.example.yaml`** → copy to **`config.yaml`** (gitignored).
- **`settings.load_app_config()`** resolves **`paths`**: `fpl_cache`, `silver`, **`my_team`** (default **`cache/my_team.json`**).
- **`model.strength_window_gw`**: **`0`** = all finished GWs in silver; **`N > 0`** = last N distinct finished GW ids (see plan / TASKS for caveats on home/away sample size).

Secrets: repo-root **`.env`** (`FPL_SESSION_COOKIE`, `FPL_X_API_AUTHORIZATION`, …) — gitignored. **`sync-team`** calls **`load_dotenv()`**.

---

## Implemented CLI (shipped)

| Command | Purpose |
|---------|---------|
| **`fplbot ingest fpl`** | Official API → versioned **`cache/fpl/<run-id>/`** + manifest; materialises **`data/silver/*.parquet`** + **`metadata.json`**. |
| **`fplbot sync-team`** | Session headers from env → normalised squad JSON at **`paths.my_team`**. **`--entry-id`**, **`--verbose`** / **`FPLBOT_LOG_HTTP`**. |
| **`fplbot model probe`** | Target GW (default: next from silver `events`): top players by **`xP_fpl`** vs **`ep_next`**; **`--gw`**, **`--top`**, **`--breakdown`**, **`--position`**, **`--team`**. |
| **`fplbot model probe-player`** | Verbose narrative for one element id; **`--gw`**. |
| **`fplbot model season-totals`** | League Σ goals / Σ assists on silver players (used to explain **`assist_scale`**). |
| **`fplbot model fixtures`** | Unfinished fixtures in GW: E[goals], λ, mode scoreline, 1X2; strength meta; **`--gw`**, **`--breakdown`** (hint to `model fixture`). |
| **`fplbot model fixture <id>`** | Deep λ / window GF–GA / μ / Poisson trace for one fixture; **`--gw`** optional but must match when set. |

---

## CLI stubs (not implemented)

These exist as Typer commands but delegate to **`NotImplementedError`** handlers: **`suggest`**, **`record`**, **`finalize-gw`**, **`report`**, **`ingest fantasy-scout`**. **`optimise/`** and **`evaluation/`** packages are placeholders for later phases.

---

## Model behaviour (high level)

- **Match layer:** Home/away attack & defence from finished fixtures in silver → **λ** per fixture (**`match_lambda`**), independent **Poisson** marginals, clean-sheet probability, 1X2 / scoreline mode (**`fixture_scores`**, **`poisson_match`**).
- **Player layer (Phase 3.5):** **`xP_fpl`** — 2025/26 FPL rules **subset** in code (`fpl_scoring_2526` + `fpl_expected_points`): goals, assists, CS, goals conceded (GK/DEF), appearance proxy, bonus + defensive-contribution **v1 proxies**; saves / cards / pens largely **0** or stubbed. **`status`** **i/s/n/u** → **0** points and excluded from share denominators for that side.
- **Goal share:** Blend of squad-normalised **`_attack_weight`** (bootstrap stats ladder) and **xG share** — see **`player_points`**, **`fpl_expected_points`**; iteration ideas in **`docs/TASKS.md`** → Later.

---

## Tests

```bash
pytest
ruff check src tests && ruff format --check src tests
```

- **`tests/fixtures/fpl/`** — small JSON for **`respx`** mocks.
- **`tests/contract/`** — live HTTP gated by **`RUN_LIVE_FPL`** (see **`tests/conftest.py`**).

---

## Git / local artefacts

Do not commit **`cache/`**, **`data/silver/`** contents, **`.env`**, **`config.yaml`**, or root **`my_team.json`** (legacy path). Tracked **`config.example.yaml`** is the template. See **`.gitignore`**.

---

## Workspace expectations for agents

Before non-trivial work on this project, read **`docs/FPL_BOT_PLAN.md`** (canonical spec). If that path is missing, search for `FPL_BOT_PLAN.md`.

### Non-negotiables

1. **Advisory only** — no auto-submit to the FPL site; session cookies / secrets only in **`ingest.team_snapshot`** + env (see `docs/SYNC_TEAM.md`).
2. **Modular pipelines** — separate `ingest.fpl`, `ingest.fantasy_scout`, optional future `ingest.*`; silver layer; optimiser has no HTTP.
3. **Evaluation** — every `suggest` / `record` creates a **`run_id`** with:
   - **All prediction inputs**: content-addressed raw payloads, `my_team.json`, frozen config, git SHA, **materialised silver / predictor inputs** (not "rebuild from main").
   - **All useful predictions**: per-player expected points (primary), fixture/team model outputs, recommended 15/XI/captain/transfers and expected totals.
4. **Post-GW** — `finalize-gw` joins **actuals** for back-analysis.

### Implementation hints

- **Official FPL API only** for ingest: **`httpx`** + owned/partial models in `ingest.fpl`
- **Silver** materialisation: **Parquet** under `data/silver/`; **SQLite** in **Phase 5b** for `runs` / predictions / actuals (plan §3.4, §5.5).
- **Chips** and **odds** are **out of v1 optimiser** unless the plan phase says otherwise.

---

## Further reading

- **`README.md`** — install, CLI examples, auth.
- **`docs/SYNC_TEAM.md`** — `sync-team` and headers.
- **`.opencode/opencode.json`** — opencode agent configuration for this workspace.

When behaviour or scope changes materially, update **`docs/FPL_BOT_PLAN.md`** and checkbox state in **`docs/TASKS.md`**.

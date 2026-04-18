# FPL Advisory Bot — Project Plan

Canonical specification for a **local Python** tool that supports **official Fantasy Premier League (UK)** for **one team**, in **advisory mode only** (recommendations; human applies changes on the site).

**Repository:** `/Users/mhammond/personal/fantasy-bot`

---

## 1. Goals and constraints

| Item | Decision |
|--------|----------|
| Mode | **Advisory** — no auto-submit |
| Scope | **One** FPL entry |
| Language | **Python** |
| Runtime | **Local** (CLI; optional cron / launchd) |
| Chips (wildcard, FH, BB) | **Phase 2** — not in optimiser v1 |
| Betting odds | **Deferred** — research sources, ToS, vig removal; `OddsSource` stub until then |
| Paid “expected points” APIs | **Out of scope** — use free data + own models |
| Third-party fetch (Scout, injuries, etc.) | Only where **allowed**; each source behind its own adapter |
| Official FPL HTTP | **`httpx` + owned/partial Pydantic models** in `ingest.fpl` against the **public FPL JSON API**. **No** third-party **`amosbastian/fpl`** wrapper — same endpoints, less dependency churn; adapter stays **raw-HTTP-first** unless we explicitly revisit. |
| Phase 2 session (Classic) | **`FPL_SESSION_COOKIE`** (+ usually **`FPL_X_API_AUTHORIZATION`**, optionally **`FPLBOT_SYNC_USER_AGENT`**) in **gitignored** repo-root **`.env`** or the shell — see root **`README.md`** (Authenticated `sync-team`). **`fplbot sync-team`** calls **`load_dotenv()`**. **No** Playwright / automated login — you copy headers from a real browser session. |
| Phase 2 entry id | **`fpl.entry_id` in `config.yaml`**; **`fplbot sync-team --entry-id N`** overrides for one run. |
| `my_team.json` | **Owned, versioned normalised schema** (not a raw API dump only) so downstream models stay stable if the API shape drifts. |
| Authenticated FPL usage | **Manual** `sync-team` only — no background sync daemon or high-frequency polling in v1. |

**Compliance note:** Review FPL and third-party **terms** before any automated fetching. Keep **credentials isolated** in a small module; everything else should work from **cached artefacts**.

---

## 2. Modelling approach

### 2.1 Team strength and fixtures

- **Primary signal for expected goals / match rates:** team **home / away** **goals and/or xG** (scored and conceded) **relative to league baselines**, with **shrinkage** toward league average (empirical-Bayes style).
- **Fixture λ** from **home/away** goal rates vs **μ_home** / **μ_away** (home attack × away defence × μ_home, and the away mirror). **No** configurable ``home_advantage`` scalar on λ, **no** FPL fixture-difficulty nudge on λ; third-party scout feeds remain optional **adapters** for later UX, not multipliers on λ.
- **Strength window (defaults):** team rates use **all finished fixtures in silver** (``strength_window_gw: 0``). A positive value caps to the last N distinct GW ids for experiments. **Later / form:** recency weighting or per-venue windows (e.g. last N home and last N away fixtures) — a pure “last 6 GWs” cap yields only ~3 home games in the sample, which is awkward for home/away-split λ; see **TASKS** “Recency / form”.
- **xG vs goals:** prefer a **blend** (e.g. more xG when sample size is small; more weight on actual goals as the season grows), if both feeds exist.

### 2.2 Start of season / bootstrap

- **Priors** from **previous season** team strengths, **heavily shrunk** toward league average.
- **Promoted teams:** map to a **generic promoted prior** or league mean until enough GWs accrue.
- **Uncertainty:** **widen** early-season distributions so the optimiser does not overfit thin evidence.

### 2.3 Goal distribution (match layer)

- **v1:** **Independent Poisson** per side for goals given λ_home, λ_away from the ratio model.
- **Later:** **Dixon–Coles** (low-score correlation) and/or **odds-implied** distributions via `OddsSource`.

### 2.4 Player layer

- **Team** goal / clean-sheet / conceded expectations → **player** points via **historical share** of team goals/assists (and **minutes / availability** gating).
- **Own goals, cards:** **ignore** or **league-average rare-event** priors in v1 — no deep causal model required initially.

### 2.5 FPL-calibrated expected points (**Phase 3.5**)

Early Phase 3 used a **non-FPL `xP` toy scale** for experiments; the shipped metric is **`xP_fpl`**: **expected FPL points** per player for a target gameweek, from **(a)** **match expectations** (λ, Poisson-style goals / clean sheets / conceded, etc.), **(b)** **player allocation** heuristics driven mainly by **silver bootstrap** season-to-date fields, and **(c)** **scoring rules** aligned to the current FPL season in **code + tests** (not duplicated here).

**Intent:** keep the plan at **contract level** — *what* we deliver (interpretable expected points, structured breakdown, CLI for inspection). **How** (exact buckets, proxies, assist scaling, minutes weighting, probe flags) lives in **`src/fplbot/models/`**, **README**, and **`docs/TASKS.md`** so it can evolve without rewriting this document every tweak.

**Outputs:** projections suitable for **Phase 4 `suggest`**, evaluation, and comparison to **`ep_next`** / **realised** points once **Phase 5b** exists.

---

## 3. Architecture (modular)

**Flow:** `ingest.*` (each runnable alone) → **normalised silver layer** → **projections / match model** → **optimiser** (pure) → **CLI / reports**.

### 3.1 Ingestion modules

| Module | Responsibility |
|--------|----------------|
| `ingest.fpl` | Official FPL JSON; versioned cache under e.g. `cache/fpl/` |
| `ingest.team_snapshot` | **One-off authenticated** flow; writes **`my_team.json`** (15 players, bank, free transfers). Only this touches session secrets |
| `ingest.fantasy_scout` | Optional; parse/fetch allowed Scout data; join to **FPL player ids** |
| Future `ingest.*` | Injuries, predicted XIs — one adapter per source |

**`paths.my_team` (working file) vs history:** The normalised squad JSON at **`paths.my_team`** (e.g. **`cache/my_team.json`** in the example config) is **overwritten** on each **`sync-team`** — it is only the **latest** operational snapshot for the CLI. Long-term provenance (“what squad did the model see at this deadline?”) is **Phase 5b**: each **`suggest`** / **`record`** run persists an **exact copy** or **content-addressed hash** (+ dedupe pointer) of that JSON in **`data/artifacts/…`** and links it from **`runs`** (**§5.2**), so a later sync cannot erase inputs tied to a past **`run_id`**.

Commands should be **independent** (e.g. `python -m fplbot ingest fpl`) so one failure leaves last-good cache usable.

### 3.2 HTTP client (`ingest.fpl`)

- **`httpx`** against the **official** endpoints (e.g. bootstrap-static, fixtures). **Owned** (partial) **Pydantic** models with `extra="ignore"` where practical so JSON shape drift does not brick the pipeline.
- **No** `amosbastian/fpl` (or similar): it does not add capability for public reads; keep **one** clear stack (`httpx` → cache → silver).
- If authenticated flows in Phase 2 need helpers, prefer **explicit** `httpx` + documented cookie handling in `ingest.team_snapshot`, not a hidden wrapper.

### 3.3 Provider-style interfaces (indicative names)

Implementations are swappable; downstream code depends on **types + interfaces**, not raw HTML.

- `FplBootstrapSource` — players, teams, fixtures, events, prices
- `TeamStateSource` — reads **`paths.my_team`** (latest **`sync-team`** snapshot; §5.2 freezes a copy per run)
- `TeamStrengthSource` — attack/defence parameters home/away
- `FixtureLambdaSource` — λ_home, λ_away per fixture (home/away split strengths)
- `GoalDistributionModel` — Poisson (v1); later Dixon–Coles or odds-implied
- `PlayerInvolvementModel` — team outcomes → player goal/assist / CS components
- `RareEventsModel` — stub / league averages for OG, cards
- `ScoutOverlaySource` — optional scout / narrative columns (not applied to core λ today)
- `ExtensionSource` — injuries, predicted XIs (later)
- `OddsSource` — **stub / No-op** until researched

### 3.4 Silver / warehouse layer

Merge FPL core + optional overlays into **one normalised dataset**. **Optimiser and predictor read silver**, not three different JSON shapes.

**Format (decision):** materialise silver as **Parquet** under e.g. **`data/silver/`** (per-table files such as `players.parquet`, `teams.parquet`, `fixtures.parquet`, `events.parquet`). Rationale: columnar data matches projection/model work, notebooks, and **per-run snapshots** (copy or hash a folder of Parquet files alongside artefacts in Phase 5b). Use **`pyarrow`** (or a thin Polars layer if we add it later) as the writer/reader; include a small **`silver_schema_version`** in sidecar metadata so layout changes are detectable.

**Evaluation store (Phase 5b, separate concern):** relational **`runs`**, predictions, and actuals stay in **SQLite** as in §5.5 — joins and append-only history — **not** a substitute for bulk silver tables; import from Parquet when building a run if needed.

---

## 4. Optimiser (v1)

- Starting **XI**, **bench order**, **captain** and **vice**
- **0–2 free transfers** with hit logic
- **No chips** in v1

**Phase 2:** wildcard / free hit / bench boost as separate **strategy modes** using the same data layer.

---

## 5. Evaluation, logging, and back-analysis

**Goal:** Reproduce “what the system believed” before a deadline and compare to **post-GW actuals**, with emphasis on **per-player predicted points**, while retaining enough structure to experiment with **XI / transfer logic** separately from projection quality.

### 5.1 Every `suggest` / `record` run gets a `run_id`

Append-only **`runs`** row: timestamp, GW id, deadline reference, **git commit** (or dirty metadata), **full config** (or config hash).

### 5.2 Store **all inputs** to predictions (reproducibility)

The **live** file at **`paths.my_team`** is mutable; each run below **freezes** what that run actually consumed (so item 2 is not “trust whatever is on disk now”).

For each `run_id`, persist **immutable artefacts** sufficient to recompute predictions:

1. **Raw source payloads** used (FPL bootstrap, fixtures, element summaries, etc.) — store bytes under **content-addressed paths** `data/artifacts/<sha256>/...` or equivalent.
2. **Exact copy** of **`my_team.json`** (or hash + pointer to deduped artefact).
3. **Optional sources** (Scout, injuries) as fetched, same artefact pattern.
4. **Model parameters** — frozen config (windows, shrinkage, blend weights, enabled providers).
5. **Silver / predictor inputs** — materialised snapshot (e.g. `predictor_inputs.parquet` or equivalent) **per run**, not only “rebuild from code” — code changes must not erase history.
6. **Provenance** — CLI command, hostname optional, schema version.

**Deduplication:** artefacts keyed by **hash**; `runs` stores **list of input hashes** so identical inputs across GWs do not duplicate disk.

### 5.3 Store **all relevant predictions** (outputs)

| Layer | Examples |
|--------|-----------|
| **Player** (primary analysis) | Expected points per player (mean; optional variance); optional decomposition (minutes, start prob, goal share, defensive component) |
| **Fixture / team** | λ_home, λ_away; summaries of goal distributions; P(clean sheet) etc. if derived |
| **Squad / optimisation** | Recommended 15, starting XI, bench order, captain/vice, transfers in/out, expected delta vs baseline, expected team total |

Schema sketch (conceptual):

- `artifacts` — `hash`, `kind`, `path` / storage ref
- `runs` — `run_id`, `gw`, `created_at`, `git_sha`, `config`, `artifact_hashes[]`
- `player_predictions` — `(run_id, player_id, gw, …)`
- `fixture_predictions` — `(run_id, fixture_id, gw, …)`
- `lineup_recommendation` — `(run_id, …)` (XI, bench, captain, transfers JSON or normalised tables)

### 5.4 Post-GW finalisation

Job **`finalize-gw <gw>`** (after official scores available): fill **actual** player points, minutes, bonus, etc., keyed by `(player_id, gw)` and joinable to `run_id` for calibration (MAE, rank metrics, charts).

### 5.5 Storage technology

**v1:** SQLite (`data/history/decisions.sqlite`) **or** JSONL per GW — team preference; SQLite simplifies joins across `runs`, predictions, and actuals.

---

## 6. CLI (indicative)

- `ingest fpl` / `ingest fantasy_scout` (optional)
- `sync-team` — authenticated snapshot → `my_team.json`
- `model probe` / `model probe-player` / `model fixtures` / `model season-totals` — **inspection** of silver-backed projections (**`xP_fpl`** and related); **flags and examples** → root **README**
- `suggest` — read caches + team file → write report + **evaluation `run`**
- `record` — optional explicit snapshot without full suggest
- `finalize-gw <gw>` — pull post-GW actuals into evaluation tables
- `report` — render Markdown/HTML from last run or specified `run_id`

---

## 7. Phased delivery

| Phase | Deliverable |
|-------|-------------|
| **0** | Repo skeleton: `pyproject.toml`, package layout, `cache/`, `data/`, README (advisory-only) |
| **1** | `ingest.fpl` (**httpx**, official API) + **Parquet** silver + tests |
| **2** | `sync-team` → `my_team.json`; `TeamStateSource` |
| **3** | Team strength + Poisson v1 + player projection path to the CLI (**toy `xP`** removed from shipped UX once **3.5** landed) |
| **3.5** | **`xP_fpl`** (FPL-style expected points + breakdown); probe / fixtures / sanity commands for humans and calibration |
| **4** | `suggest` + human-readable report **(reads `xP_fpl` from 3.5)** |
| **5** | Optimiser v1 (no chips) |
| **5b** | **Evaluation store**: artefacts, `runs`, player/fixture/lineup predictions, `finalize-gw` |
| **6** | Optional `ingest.fantasy_scout` + overlay |
| **7** | Free extensions: injuries, predicted XIs (`ingest.*` + `ExtensionSource`) |
| **8** | Distribution upgrade (Dixon–Coles) and/or `OddsSource` after research |
| **9** | Chips |
| **10** | Polish: logging, dry-run defaults, optional scheduling |

---

## 8. Deferred / research tracks

- **Betting odds:** legal/stable ingestion, vig removal, mapping to λ or full scoreline law
- **Rich card/OG models** — only if needed

---

## 9. Cursor usage

- **Canonical spec:** `docs/FPL_BOT_PLAN.md` — use **`@docs/FPL_BOT_PLAN.md`** (or `@FPL_BOT_PLAN.md`) in Cursor chat for full context.
- **Project rule:** `.cursor/rules/fpl-bot.mdc` — non-negotiables (modularity, advisory-only, evaluation inputs/outputs). **`alwaysApply: true`** so every conversation in this repo loads it.

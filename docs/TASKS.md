# Getting started — task list

Use this as a **checkbox backlog**. Order matters early on (Phase 0 → 1 → 2). Later phases can parallelise once ingest is solid.

**Current:** **Phase 3.5 — `xP_fpl`** is **implemented** (2025/26 subset: goals, assists, CS, conceded, appearance, bonus + defensive-contribution **v1 proxies**, pipeline + **`model probe`** / **`probe-player`** / **`season-totals`** / **`model fixtures`** / **`model fixture`**). **Next:** **Phase 4** **`suggest`** (and remaining 3.5 polish: richer scoring tests, smoke vs `ep_next`, optional second ruleset in config).

**Canonical spec:** [FPL_BOT_PLAN.md](./FPL_BOT_PLAN.md)

## Keeping plan and tasks in sync

| If you… | Update |
|----------|--------|
| Change **scope, architecture, or “what we decided”** | **`FPL_BOT_PLAN.md` first**, then adjust **`TASKS.md`** (add/remove/reorder checkboxes, or add a “Later” note). |
| Finish work or discover a **small implementation step** not worth a plan change | **`TASKS.md` only** (check boxes, add sub-bullets under the right phase). |
| Add a **new phase or defer something** | **`FPL_BOT_PLAN.md`** §7 table + **`TASKS.md`** “Later” section. |

**Rule of thumb:** *Plan = contracts and phases. Tasks = granular work.* One source of truth for **decisions** (the plan); the task list is allowed to be **more detailed and messier** than §7 as long as it does not **contradict** the plan.

**When working with AI agents:** In chat, say things like *“Implement X; update TASKS checkboxes; if this changes a project decision, update FPL_BOT_PLAN too.”* If you only touch code, at least tick **`TASKS.md`** in the same PR so the paper trail matches reality.

**Low ceremony option:** After any meaningful change, one line in git commit body: `Docs: plan` / `Docs: tasks` / `Docs: plan+tasks` so you can see when both moved.

---

## Before code

- [x] Open this folder as the project root (`fantasy-bot`)
- [x] `git init` (if not already a repo); add `.gitignore` for `cache/`, `data/`, `.env`, root `my_team.json` (legacy `paths.my_team` override), `__pycache__/`, `.venv/` (default squad snapshot lives under `cache/` → covered by `cache/*`)
- [ ] Skim `FPL_BOT_PLAN.md` once so the architecture words stop sounding like cult jargon

---

## Phase 0 — Skeleton

- [x] `pyproject.toml` — package name **`fplbot`**, Python **3.12+**, deps: `httpx`, `pydantic`, CLI **`typer`**; dev: `pytest`, **`ruff`** (check + format)
- [x] Package layout — **`src/fplbot/`** (`.python-version` + README use **pyenv** for 3.12)
- [x] Modules matching plan: `ingest/fpl.py`, `silver/`, `models/`, `optimise/`, `cli/`, `evaluation/`; **`commands/`** stubs per CLI entrypoint; ingest fpl delegates `commands` → `ingest.fpl`
- [x] `README.md` — advisory-only disclaimer, pyenv + venv install, pointer to `docs/`
- [x] `config.example.yaml` — paths + `fpl` + `model` keys actually loaded by `settings.py`
- [x] **Smoke tests** — import package; CLI `--help` and **`--version`** without a subcommand

---

## Phase 1 — FPL ingest + silver

**Decisions (see plan §1, §3.2, §3.4):** **`httpx`** only against the **official FPL JSON API** — **no** `amosbastian/fpl`. Silver on disk: **Parquet** under **`data/silver/`** (`pyarrow`); evaluation/RDBMS is **Phase 5b SQLite**, not Phase 1.

- [x] `ingest fpl` command — **`httpx`** fetch: **bootstrap-static** + **fixtures** (`ingest/client.py`, `ingest/fpl.py`, `fplbot ingest fpl`)
- [x] **Versioned cache** under `cache/fpl/<UTC-run-id>/` + root **`manifest.json`** (paths + sha256); prior runs kept on disk
- [x] **Silver** — Parquet: `events.parquet`, `teams.parquet`, `players.parquet`, `fixtures.parquet` + **`metadata.json`** (`silver_schema_version`, `ingested_at`, `fpl_cache_run_id`)
- [x] Tests — mocked **`respx`** + `tests/fixtures/fpl/`; live contract **`tests/contract/`** gated by **`RUN_LIVE_FPL`** (`tests/conftest.py`)

---

## Phase 2 — Team snapshot

**Done:**

- [x] **`docs/SYNC_TEAM.md`** — decisions, compliance, code map; points at root **README** for `.env` / DevTools (no secrets in repo)
- [x] **`ingest/team_snapshot.py`** — **`GET /api/entry/{id}/`**, **`GET /api/my-team/{id}/`**, **`GET /api/entry/{id}/transfers-latest/`**; browser-like headers; **`Cookie`** from **`FPL_SESSION_COOKIE`**; **`FPL_X_API_AUTHORIZATION`** → **`X-Api-Authorization`** (often required for **`my-team`**); optional **`FPLBOT_SYNC_USER_AGENT`**
- [x] **`team_state/`** — **`TeamStateSource`**, **`FileTeamStateSource`**, **`read_my_team_json`**, normalised snapshot schema (`snapshot_schema.py`)
- [x] **`paths.my_team`** — from `config.yaml`; default **`cache/my_team.json`**; **`mkdir(parents=True)`** before write
- [x] **`sync-team`** — **`fpl.entry_id`** + CLI **`--entry-id`** override → normalised JSON on disk
- [x] **`load_dotenv()`** before **`sync-team`** + **`python-dotenv`**
- [x] **Root README** — **Authenticated `sync-team` (`.env`)** section: template + how to copy **Cookie** / **X-Api-Authorization** from DevTools (no helper script)
- [x] CLI **`--verbose`** / **`FPLBOT_LOG_HTTP`**, success summary, **`tests/test_sync_team.py`** (mocked **`respx`**)

**Optional docs (maintainer-only):**

- [ ] **Document the normalised squad JSON** — table or short doc: each field in the on-disk snapshot (see **`team_state/snapshot_schema.py`** / what **`sync-team`** writes) ↔ source field(s) from FPL **`/api/my-team/{id}/`**, **`/api/entry/{id}/`**, **`transfers-latest`**, and any transforms. Put it in **`docs/SYNC_TEAM.md`** or a dedicated **`docs/MY_TEAM_JSON.md`** if it gets long. Skip until a human or downstream tool needs more than the Pydantic models + **`ingest/team_snapshot.py`**.

---

## Phase 3 — Models v1

**Canonical spec:** [FPL_BOT_PLAN.md](./FPL_BOT_PLAN.md) §2–§3.3. Interfaces use **`typing.Protocol`** (or thin ABCs) under **`src/fplbot/models/`**; **no HTTP** in model code — read **`paths.silver`** Parquet + **`metadata.json`** only.

### Locked decisions (agreed)

| Topic | Choice |
|--------|--------|
| **Player layer v1** | **(A)** Widen **`Element`** / **`players.parquet`** with **season-to-date** fields already on FPL bootstrap (e.g. goals, assists, minutes, xG-ish columns where the API provides them) and use **simple rules** for shares + crude minutes / availability gating — **no** new per-GW history ingest in Phase 3. |
| **Target gameweek** | **Default:** FPL **next** GW from **`events.parquet`** (`is_next` / agreed rule). **Override:** CLI flag (e.g. **`--gw N`**) on the probe command (and later **`suggest`**) for backtests / what-if. |
| **Numerics** | Prefer **`numpy`** (and **`scipy.stats`** where it saves noise) so Poisson / future Dixon–Coles or calibration do not fight hand-rolled special functions. |
| **CLI** | Add a small **`fplbot …`** command early (e.g. **`model probe`** or **`debug-xp`**) to print **top-N by projected xP** for the target GW — try-out surface before Phase 4 **`suggest`**. |

**Out of scope for v1** (previous-season priors, promoted handling, rolling player history, full xG/goals blend): see **Later → Modelling / data**.

### Implementation order (check off as shipped)

**Data / silver**

- [x] Extend **`Fixture`** (+ tests + **`min_fixtures.json`**) with finished-match fields needed for team rates (**`team_h_score`**, **`team_a_score`**, keep nullable pre-kickoff).
- [x] Extend **`Element`** with optional **season-to-date** stats from bootstrap JSON (goals, assists, minutes, xG-ish, **bonus**, **defensive_contribution**, **defensive_contribution_per_90**, etc.); bump **`SILVER_SCHEMA_VERSION`** in **`silver/writer.py`** when schema changes; doc trail here until **`docs/MODELS_V1.md`** exists.
- [x] **`pyproject.toml`** — add **`numpy`** and **`scipy`**.

**Models**

- [x] **`models/silver_io`** — load silver tables, read **`metadata`**, resolve **target GW** (default next, respect override from CLI caller).
- [x] **Team rate table** — **`team_strength.build_team_rates`**: goal averages over **all finished GWs in silver** by default (``strength_window_gw: 0``); optional last-N cap → explicit **λ** ratios; Poisson **1X2** from score grid.
- [x] **λ per fixture** — **`match_lambda.lambdas_for_fixture`** using home/away split rates × ``μ_home`` / ``μ_away`` (no HA scalar, no FDR on λ).
- [x] **Poisson / CS** — **`poisson_match.clean_sheet_prob`** via **`scipy.stats.poisson`** (v1 marginal).
- [x] **Player layer** — was toy ``project_players_for_fixture``; superseded by **`fpl_expected_points.project_fpl_points_for_fixture`** (Phase 3.5).
- [x] **Output** — **`pipeline.PlayerProjection`** + **`project_gw`** for one target GW.

**CLI + tests**

- [x] **`fplbot model probe`** — **`--gw`** / **`--top`** / **`--breakdown`** / **`--position` (`-p`)** / **`--team` (`-t`)**; uses **`load_app_config()`** (paths + **`cfg.model`**).
- [x] **`fplbot model fixtures`** — unfinished fixtures in the target GW: expected goals, λ, mode scoreline, 1X2; prints strength meta (**μ**, finished-fixture counts, **`strength_window_gw`**); **`--gw`**; **`--breakdown`** adds a one-line **`model fixture …`** hint per row.
- [x] **`fplbot model fixture <id>`** — deep trace: window GF/GA (venue + league context), μ, λ construction, Poisson breakdown (`commands/model_fixtures.py`); optional **`--gw`** must match the fixture when set.
- [x] **`tests/test_models_phase3.py`**, **`tests/test_team_rates_window.py`**, **`tests/test_match_lambda.py`** (+ ingest fixture updates where needed); no live FPL in model unit tests.

**Deliverable parity:** crude **per-player xP** for a chosen GW from latest silver, callable via **`fplbot model probe`**. Protocols in **`models/protocols.py`** document intended swappable surfaces; concrete code is functional for v1.

---

## Phase 3.5 — FPL-calibrated expected points (`xP_fpl`)

**Spec:** [FPL_BOT_PLAN.md](./FPL_BOT_PLAN.md) §2.5 + §7 row **3.5**. **Toy `xP`** was dropped from default types / CLI in favour of **`xP_fpl`** (keep any leftover test helpers only if still useful).

**Rules & types**

- [x] **`fpl_scoring_2526`** — constants / helpers for **2025/26** (goals, assists, CS, conceded expectation); official link in module docstring. **Multi-season config** = later.
- [ ] **Unit tests** — richer table-driven cases (e.g. MID 90+1 goal + CS + 0 conceded); basic tests in **`tests/test_fpl_scoring_2526.py`**.

**Match expectations (from existing λ)**

- [x] **`P(clean_sheet)`** — via existing ``clean_sheet_prob`` / Poisson.
- [x] **`E[goals_conceded_points]`** for GK/DEF — ``expected_goals_conceded_points`` (−E[⌊G/2⌋]).

**Player allocation**

- [x] **Goals / assists** — team **λ** × blended **attack weight** and **xG/xA** squad shares (v1 heuristic).
- [x] **Assist team budget** — ``assist_mass = λ × assist_scale`` where **``assist_scale``** = silver **Σassists / Σgoals_scored** (fallback **0.95** if no goals); split by xA-based **``assist_share``** (no legacy **0.55** / **4.5** cap).
- [ ] **Appearance** — v1 uses **``min(2, 1 + minutes_w)``** proxy, not true **P(60+) / P(1–59)**; **``minutes_w``** = season minutes ÷ **``(90 × team's finished fixture count)``** from silver ``fixtures`` (clamped); refine later (see **Later § minutes**).
- [x] **CS / conceded** — position CS from **P(CS)**; conceded expectation split among GK/DEF by minutes weight.
- [x] **GK saves** — stub **0** (no saves field on ``Element`` yet); documented via breakdown line.
- [x] **Bonus + 2025/26 defensive contributions** — **v1 proxies** in ``xP_fpl`` (season bonus per 90 × ``minutes_w``, cap 3/GW; DC via linear threshold proxy on **``defensive_contribution_per_90``**); **cards / pens** still **0** + breakdown keys; refine in **Later**.
- [x] **Hard unavailable (v1)** — bootstrap ``status`` **i / s / n / u** → **``xP_fpl`` = 0** (and **``minutes_w`` = 0** in breakdown); those players **excluded** from attack / xG / xA / DEF **share denominators** for their side in that fixture (if an entire match-day squad were hard-out we fall back to the raw squad to avoid divide-by-zero — degenerate). **Doubtful (`d`)** still uses normal ``minutes_w``. ``Element`` persists **``chance_of_playing_this_round``** / **``chance_of_playing_next_round``** for future use (not yet wired into ``xP_fpl``).

**Pipeline & CLI**

- [x] **`PlayerProjection`** — **`xP_fpl`** + **`position`** (GK/DEF/MID/FWD) + **`FPLPointsBreakdown`** (FPL buckets + model fields).
- [x] **`model probe` (default)** — compact table: **id**, **pos**, name, **``xP_fpl``**, ``ep_next``, fixture; short key.
- [x] **`model probe --breakdown`** — FPL bucket line + model line (**``assist_scale``**, λ, shares, …).
- [x] **`model probe --position` / `--team`** — filter sorted projections **before** **`--top`** cap (position = GK/DEF/MID/FWD; team = short name case-insensitive or numeric **``team_id``**).
- [x] **`model probe-player <id>`** — full narrative (includes **pos**); ``--gw`` optional.
- [x] **Remove legacy toy `xP`** from probe / projection (``project_players_for_fixture`` removed).
- [ ] **`config.yaml`** — optional **`model.fpl_points_season`** when a second ruleset exists.

**Quality**

- [ ] **Smoke sanity** — GW-level mean/variance of `xP_fpl` vs **`ep_next`** (not identical, not orders of magnitude apart).

---

## Phase 4 — Suggest + report

**Depends on:** Phase **3.5** **`xP_fpl`** as the projection input.

- [ ] `suggest` — load latest silver + **`paths.my_team`** (default **`cache/my_team.json`**) → call models → print / write Markdown report
- [ ] Human-readable diff vs current 15 (who to bench, captain suggestion)

---

## Phase 5 — Optimiser v1

- [ ] XI + bench + captain/vice under FPL rules
- [ ] 0–2 transfers with hit; no chips

---

## Phase 5b — Evaluation store

- [ ] `runs` + content-addressed `artifacts/`; store **all inputs** + **all predictions** per `suggest`
- [ ] `finalize-gw` — attach actuals after GW
- [ ] Minimal notebook or script: join pred vs actual for one player (sanity check)

---

## Later (do not block v1)

**Modelling / data (deferred from Phase 3 v1 — aligns with [FPL_BOT_PLAN.md](./FPL_BOT_PLAN.md) §2.1–§2.2):** when any ship, touch **`FPL_BOT_PLAN.md`** §2 / §7 if behaviour changes materially.

- [ ] **Previous-season team priors** — import or cache last season’s team rates; shrink toward league mean on GW1; wire into `TeamStrengthSource` (or a prior layer).
- [ ] **Promoted clubs** — explicit detection + generic promoted prior (or mapped decay) instead of “few games → more shrink toward league average” only.
- [ ] **Per-GW element history** — extra official endpoints (or derived rolls) so player shares use rolling form inside the season, not only bootstrap season totals.
- [ ] **Minutes / availability (`minutes_w`)** — v1 is still crude: season minutes ÷ ``(90 × team's finished fixture count from silver)``, clamped. **Future ideas:** ingest **per-fixture element minutes** and derive **rolling mean/median minutes** or **P(60+) / P(1–59)**; fold **``chance_of_playing_*``** (already on ``Element``) with **``status``** / **``news``**; **DGW**-aware “possible minutes this GW” instead of a single scalar; optional **Bayesian / shrink** for low ``n``; wire through appearance + every bucket that multiplies by ``minutes_w``.
- [ ] **Availability & lineups (multi-source)** — go beyond hard **i/s/n/u**: optional **EPL / press / injury APIs** (ToS-compliant), **predicted XI** feeds; **fractional** expected minutes for rotation / bench vs starters; align with **`ep_next == 0`** only where it means “unavailable” (not every cheap bench FPL 0). When adding **multi-GW lookahead**, respect **return / expected-back** metadata so players are not zeroed for the whole horizon by mistake.
- [ ] **xG vs goals blend by calendar** — team λ uses both signals with a season-progress curve (plan §2.1); add `model` keys + ingest when implemented.
- [ ] **Dixon–Coles correction** — τ / ρ-style adjustment on the **joint** scoreline law (low-score dependence); augments or replaces independent Poisson marginals (plan §2.3).
- [ ] **Recency / form (team strengths)** — default is full-season-in-silver (``strength_window_gw: 0``). **Idea backlog:** (a) exponential decay / half-life on past fixtures; (b) ``strength_window_gw`` > 0 as a simple last-N **calendar** GWs cap — note that N GWs is only ~N/2 **home** samples and ~N/2 **away** samples, so short windows starve venue-specific rates; (c) **per-venue** caps instead, e.g. last 6 **home** and last 6 **away** fixtures (possibly different calendar spans); (d) blend full-season with a recency overlay. Needs design + eval before any default change.
- [ ] **Sample-size handling** — shrink per-team home/away attack & defence **rates** toward league means when in-window match counts are small (κ / pseudo-counts or hierarchical prior); complements raw ratio λ today. **Parked:** short research spike (e.g. single global τ pseudo-games-at-μ vs split attack/defence) before defaults land in `config.yaml` / `ModelParams`.
- [ ] **Goal allocation (`goal_share` / attack weights)** — v1 splits team λ using a **50/50** blend of squad-normalised **`_attack_weight`** (bootstrap **EGI** → **xG + 0.6·xA** → **goals + assists** fallback + ICT) and **xG share** (`fpl_expected_points.project_fpl_points_for_fixture`). **Explore / iterate:** stronger weight on **within-team goals scored** (or goals per 90) vs xG vs EGI; alternative blends; early-season shrink; sanity vs **`ep_next`** and post-GW realised goals by position. Touch **`player_points._attack_weight`** and goal-share logic together when changing.

**Roadmap phases:**

- [ ] Phase 6 — `ingest.fantasy_scout` + overlay
- [ ] Phase 7 — injuries / predicted XIs adapters
- [ ] Phase 8 — Dixon–Coles or `OddsSource`
- [ ] Phase 9 — chips
- [ ] Phase 10 — cron, polish



## Implementation Plan: Previous-Season Team Priors & Promoted Clubs

### Previous-Season Team Priors Implementation

**Data Acquisition:**
- [ ] Create `ingest/prior_season.py` module
- [ ] Implement historical data fetching from FPL archive/external API
- [ ] Add end-of-season snapshot functionality

**Storage Strategy:**
- [ ] Add new silver table: `season_priors.parquet`
- [ ] Schema: `season`, `team_id`, `home_attack`, `away_attack`, `home_defence`, `away_defence`
- [ ] Bump `SILVER_SCHEMA_VERSION` when adding new table

**Team Strength Integration:**
- [ ] Update `team_strength.py` to load prior season data
- [ ] Implement Bayesian blending: `blend_rates(priors, current, gw)`
- [ ] Add configuration: `prior_season_weight`, `prior_transition_gw`

### Promoted Clubs Implementation

**Identification Mechanism:**
- [ ] Create `models/promoted.py` module
- [ ] Implement `identify_promoted_clubs(current_season)`
- [ ] Cross-reference current teams with previous season standings
- [ ] Add external API fallback (football-data.org)

**Special Priors Handling:**
- [ ] Add `is_promoted` flag to team model
- [ ] Implement `apply_promoted_prior(team_id)`
- [ ] Use league average with 15% degradation for promoted clubs
- [ ] Gradual transition to actual performance data

**Configuration:**
- [ ] Add to `config.yaml`:
  ```yaml
  model:
    prior_season_weight: 0.7
    prior_transition_gw: 6
    promoted_club_degradation: 0.15
  ```

### Implementation Sequence
1. Historical data pipeline (`ingest/prior_season.py`)
2. Promoted club identification (`models/promoted.py`)
3. Team strength integration (`team_strength.py`)
4. CLI extension: `fplbot model team-strength --gw 1 --show-priors`

### External Dependencies
- [ ] Research football-data.org API integration
- [ ] Implement rate limiting and error handling
- [ ] Add configuration for external API keys

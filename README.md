# fplbot

Local **Python** tooling for the **official Fantasy Premier League**. It is **advisory only**: it may recommend transfers, captains, and lineups — **you** apply changes on the FPL site. Nothing here auto-submits picks or logs into the site except the explicit team snapshot flow when that exists (`sync-team`).

## Requirements

- **[pyenv](https://github.com/pyenv/pyenv)** (recommended) so this repo’s **`.python-version`** selects **Python 3.12.x** automatically when you `cd` here.
- Otherwise: any **Python 3.12+** on your `PATH` that satisfies `requires-python` in `pyproject.toml`.

## Install (editable)

From the repo root (pyenv will pick up `3.12` from `.python-version` if installed):

```bash
pyenv install -s 3.12                  # once per machine; -s skips if 3.12.x already installed
python -V                            # should show 3.12.x

python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[dev]"
```

## CLI

```bash
fplbot --help
fplbot ingest fpl   # Phase 1: fetch FPL JSON → cache/fpl/ + data/silver/*.parquet
fplbot sync-team    # Phase 2: .env + fpl.entry_id → paths.my_team (default cache/my_team.json)
fplbot sync-team --entry-id 1234567   # same, but entry id from CLI (overrides config)
fplbot sync-team --verbose            # log each request URL + redacted headers + status
fplbot sync-team --help               # all flags, including --entry-id and --verbose
fplbot model probe                    # default GW from silver events; top 15 by xP_fpl
fplbot model probe --gw 5 --top 10    # GW 5; show top 10 after sort
fplbot model probe --breakdown        # per player: FPL bucket line + model line (λ, shares, assist_scale, …)
fplbot model probe -p GK -t NOR -n 8  # only GK on team NOR, then take top 8 (see filters below)
fplbot model probe --team 1           # filter by numeric team id (matches silver teams.id)
fplbot model probe-player 308         # long-form breakdown for element 308 (shows GK/DEF/MID/FWD)
fplbot model probe-player 308 --gw 5  # same, for GW 5
fplbot model season-totals            # Σ goals_scored & Σ assists on silver; ratio = assist_scale in xP_fpl
fplbot model fixtures                 # λ from home/away goal-rate ratios × μ_h/μ_a; Poisson mode + 1X2 %
fplbot model fixtures --breakdown     # after each row: hint to run ``model fixture <id>`` for full trace
fplbot model fixture 339              # one fixture: window GF/GA counts, μ, λ ratios, Poisson 1X2
fplbot model fixtures --gw 5          # only fixtures not yet marked finished in that GW
```

**`model probe`** reads **`paths.silver`** and prints **`pos`** (GK / DEF / MID / FWD), **`xP_fpl`** (2025/26 rules **subset** — see `fplbot.models.fpl_scoring_2526` + `fpl_expected_points`), and official **`ep_next`**. **`--position` (`-p`)** keeps one line of **`GK`**, **`DEF`**, **`MID`**, or **`FWD`** (case-insensitive). **`--team` (`-t`)** keeps players whose **`team_short`** matches (case-insensitive) or whose **`team_id`** equals the value if you pass digits. Filters apply **after** sorting by **`xP_fpl`**, **before** the **`--top`** cap. **`--breakdown`** adds expected points per bucket (appearance through **bonus**) plus internals such as **`assist_scale`** (league Σassists/Σgoals from silver). Players with bootstrap **`status`** **i** (injured), **s** (suspended), **n** (not in squad next GW), or **u** (unavailable) get **`xP_fpl` = 0** for that projection (v1); doubtful and rotation are still TODO — see **`docs/TASKS.md`** Later § availability.

Details: [docs/SYNC_TEAM.md](docs/SYNC_TEAM.md).

**`model fixtures`** / **`model fixture`** are for **match-layer** λ and Poisson sanity (window totals, μ, 1X2), not player **`xP_fpl`**. Other top-level commands (`suggest`, optimiser, …) stay stubbed until their phase — see [docs/TASKS.md](docs/TASKS.md).

## Authenticated `sync-team` (`.env`)

`fplbot sync-team` loads **`python-dotenv`** from a **repo-root** **`.env`** (shell exports still win if already set). Put secrets only there — **`.env`** is gitignored.

In **Chrome DevTools → Network**, choose a request to **`fantasy.premierleague.com`** where **`/api/my-team/`** or your **picks** call returns **200** (while you are logged in). Open **Headers** and copy:

1. **`Cookie`** — the full value after `Cookie: ` (one long line of `name=value; …`).
2. **`X-Api-Authorization`** — the full value after that header name (often required; without it **`my-team`** may **403** even with a valid cookie).
3. Optionally **`User-Agent`** — same row, if you still see **403**; set as **`FPLBOT_SYNC_USER_AGENT`** (see [docs/SYNC_TEAM.md](docs/SYNC_TEAM.md)).

**`.env` template** (double quotes; escape any `"` inside the value as `\"`):

```dotenv
# Repo root only. Never commit.

FPL_SESSION_COOKIE="paste-full-cookie-string-here"

FPL_X_API_AUTHORIZATION="Bearer foobar"

# Optional if my-team still 403:
# FPLBOT_SYNC_USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
```

Then from the repo root: **`fplbot sync-team`** (and **`--entry-id`** or **`fpl.entry_id`** in `config.yaml` as needed).

## Configuration

Copy `config.example.yaml` to `config.yaml` and adjust paths. Keep **credentials** out of git; the squad snapshot defaults to **`cache/my_team.json`** (under **`cache/*`**, already ignored).

Team strengths for λ default to **all finished gameweeks in silver** (`model.strength_window_gw: 0`). Set a positive integer to use only the last N distinct GWs (e.g. `6` for a short rolling window).

## Documentation

- **Repo map (for contributors / agents):** [AGENTS.md](AGENTS.md)
- **Canonical spec:** [docs/FPL_BOT_PLAN.md](docs/FPL_BOT_PLAN.md)
- **Task checklist:** [docs/TASKS.md](docs/TASKS.md)
- **`sync-team` / auth (Phase 2):** [docs/SYNC_TEAM.md](docs/SYNC_TEAM.md)

## Compliance

Review FPL and third-party **terms** before automated fetching. Prefer working from **cached** artefacts where possible.

## Tests

**Default (CI / quick):** mocked HTTP only — no calls to FPL.

```bash
pytest
```

**Live HTTP contract** (hits `fantasy.premierleague.com`; **ignored** unless `RUN_LIVE_FPL` is truthy — see `tests/conftest.py`):

```bash
RUN_LIVE_FPL=1 pytest tests/contract/
```

## Lint / format

```bash
ruff check src tests
ruff format src tests
```

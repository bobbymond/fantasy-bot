"""``fplbot model`` — projection probe (Phase 3)."""

from __future__ import annotations

import typer

from fplbot.commands import model_fixtures as model_fixtures_mod
from fplbot.commands import model_probe as model_probe_mod
from fplbot.commands import model_probe_player as model_probe_player_mod
from fplbot.models.season_snapshot_stats import (
    league_goals_assists_totals,
    read_players_rows,
)
from fplbot.settings import load_app_config

model_app = typer.Typer(
    name="model",
    help="Match and player projection models (Phase 3 / 3.5).",
    no_args_is_help=True,
)


@model_app.command("fixtures")
def _fixtures(
    gw: int | None = typer.Option(
        None,
        "--gw",
        help="Gameweek id (default: FPL ``is_next`` from silver ``events``).",
    ),
    breakdown: bool = typer.Option(
        False,
        "--breakdown",
        help="After each row, print ``fplbot model fixture <id>`` for full λ trace.",
    ),
) -> None:
    """Predicted goals / likely scorelines for unfinished fixtures in that GW."""
    try:
        gw_id, rows, sm = model_fixtures_mod.run(gw=gw)
    except FileNotFoundError as exc:
        typer.echo(f"model fixtures: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(
        f"model fixtures: gameweek {gw_id} — "
        f"{len(rows)} upcoming (unfinished) fixture(s)"
        + ("  (--breakdown on)" if breakdown else "")
    )
    gmin, gmax = sm["gameweek_min"], sm["gameweek_max"]
    span = f"{gmin}–{gmax}" if gmin is not None else "—"
    n_in = int(sm["n_distinct_gws_in_window"])
    n_all = int(sm["n_finished_gws_silver"])
    sw = int(sm["strength_window_gw"])
    if n_all == 0:
        typer.echo(
            "  strength: silver has no finished fixtures with both scores and a GW "
            f"(event). Baseline μ_h=μ_a={float(sm['mu_home']):.3f}; "
            f"strength_window_gw={sw} does nothing until ingest populates results."
        )
    else:
        mh, ma = float(sm["mu_home"]), float(sm["mu_away"])
        nfx = int(sm["n_fixtures_in_window"])
        sw_note = (
            "all finished GWs in silver"
            if sw == 0
            else f"last {sw} GW(s); {n_in} of {n_all} distinct finished GWs"
        )
        typer.echo(
            f"  strength: μ_h={mh:.3f} μ_a={ma:.3f}  {nfx} finished scored fixtures  "
            f"GW span {span}  (strength_window_gw={sw}: {sw_note})"
        )
        if sm["window_uses_all_finished_gws"]:
            typer.echo(
                "  note: those GWs are the full finished history in silver — "
                "a capped window cannot exclude older data until more GWs finish."
            )
    typer.echo("  key:")
    typer.echo("       fx   FPL fixture id")
    typer.echo("       E    expected goals (Poisson mean) home-away")
    typer.echo("       λ    team scoring rates used for that fixture")
    typer.echo("       mode most likely scoreline (p = probability of that scoreline)")
    typer.echo("       1X2  home / draw / away win percentages")
    if breakdown:
        typer.echo(
            "       --breakdown  one line per row → run ``fplbot model fixture <id>`` "
            "for raw window goals + μ + λ"
        )
    for r in rows:
        label = f"{r['team_h_name']} (H) vs {r['team_a_name']} (A)"
        typer.echo(
            f"  fx {r['fixture_id']:<5}  {label:<28}  "
            f"E={r['expected_home_goals']:.2f}-{r['expected_away_goals']:.2f}  "
            f"λ={r['lambda_home']:.2f}-{r['lambda_away']:.2f}  "
            f"mode {r['mode_home_goals']}-{r['mode_away_goals']} "
            f"(p={r['mode_scoreline_prob']:.3f})  "
            f"1X2 H={100*r['prob_home_win']:.0f}% "
            f"D={100*r['prob_draw']:.0f}% "
            f"A={100*r['prob_away_win']:.0f}%"
        )
        if breakdown:
            typer.echo(model_fixtures_mod.format_fixture_compact_hint_line(r))


@model_app.command("fixture")
def _fixture_one(
    fixture_id: int = typer.Argument(
        ...,
        help="Silver ``fixtures.id`` (same as FPL fixture id).",
    ),
    gw: int | None = typer.Option(
        None,
        "--gw",
        help="Must match the fixture's gameweek if set (omit to use fixture's GW).",
    ),
) -> None:
    """One fixture: window goal totals, μ, and full λ / Poisson breakdown."""
    try:
        pred, lb, rates, meta, fx_all = model_fixtures_mod.run_fixture_detail(
            fixture_id=fixture_id, gw=gw
        )
    except FileNotFoundError as exc:
        typer.echo(f"model fixture: {exc}", err=True)
        raise typer.Exit(1) from exc
    except ValueError as exc:
        typer.echo(f"model fixture: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"model fixture {fixture_id}")
    for line in model_fixtures_mod.format_fixture_deep_breakdown_lines(
        pred, lb, rates, meta, fx_all
    ):
        typer.echo(line)


@model_app.command("probe")
def _probe(
    gw: int | None = typer.Option(
        None,
        "--gw",
        help="Gameweek id (default: FPL ``is_next`` from silver ``events``).",
    ),
    top: int = typer.Option(
        15,
        "--top",
        "-n",
        min=1,
        help="How many players to print (sorted by xP_fpl descending).",
    ),
    breakdown: bool = typer.Option(
        False,
        "--breakdown",
        help="FPL point buckets + model lines (see docs/FPL_BOT_PLAN.md section 2.5).",
    ),
    position: str | None = typer.Option(
        None,
        "--position",
        "-p",
        metavar="POS",
        help="Only GK, DEF, MID, or FWD (case-insensitive).",
    ),
    team: str | None = typer.Option(
        None,
        "--team",
        "-t",
        metavar="TEAM",
        help="Team short name (e.g. NOR) or numeric team id; case-insensitive.",
    ),
) -> None:
    """Expected FPL points (2025/26 rules subset) for one GW from silver."""
    try:
        gw_id, rows = model_probe_mod.run(
            gw=gw, top=top, position=position, team=team
        )
    except FileNotFoundError as exc:
        typer.echo(f"model probe: {exc}", err=True)
        raise typer.Exit(1) from exc
    except ValueError as exc:
        typer.echo(f"model probe: {exc}", err=True)
        raise typer.Exit(1) from exc

    filter_bits: list[str] = []
    if position is not None and str(position).strip():
        filter_bits.append(f"position={str(position).strip().upper()}")
    if team is not None and str(team).strip():
        filter_bits.append(f"team={str(team).strip()!r}")
    suffix = f" — filters: {', '.join(filter_bits)}" if filter_bits else ""
    typer.echo(f"model probe: gameweek {gw_id}{suffix} ({len(rows)} listed, cap={top})")
    if breakdown:
        typer.echo("  key (--breakdown):")
        typer.echo("       pos column = GK / DEF / MID / FWD (same as compact probe)")
        typer.echo("       FPL buckets = expected points from that rule (zeros if N/A)")
        typer.echo(
            "       app..bonus = app, goals, ast, CS, gc, sv, defc, card, bonus (E pts)"
        )
        typer.echo(
            "       model: λ, λopp, P(cs), min_w, goal/assist share, assist_scale"
        )
    else:
        typer.echo("  key:")
        typer.echo("       pos     GK / DEF / MID / FWD")
        typer.echo("       xP_fpl  expected FPL pts (2025/26 rules subset)")
        typer.echo("       ep      FPL official ep_next from silver")
        typer.echo("       Tm/vs   team and opponent short names")
        typer.echo("       fx      FPL fixture id")
        typer.echo("       --position / --team  narrow before top-N cap")
        typer.echo("       --breakdown  short FPL + model lines per player")
        typer.echo("       probe-player ID  full narrative for one element (this)")
    for r in rows:
        name = str(r["web_name"])[:14]
        pos = str(r.get("position") or "?")[:3]
        side = "H" if r["side"] == "H" else "A"
        tm = str(r["team_short"])[:4]
        opp = str(r["opp_short"])[:4]
        fxid = int(r["fixture_id"])
        xf = float(r["xP_fpl"])
        ep = float(r["ep_next_fpl"])
        typer.echo(
            f"  {r['player_id']:>4}  {pos:<3}  {name:<14}  {tm:<4}  "
            f"xP_fpl={xf:.2f}  ep={ep:.2f}  vs {opp:<4}  {side}  fx={fxid}"
        )
        if breakdown:
            bd = r["breakdown"]
            typer.echo(
                "       FPL:  "
                f"app={float(bd['appearance']):.2f}  gl={float(bd['goals']):.2f}  "
                f"ast={float(bd['assists']):.2f}  cs={float(bd['clean_sheet']):.2f}  "
                f"gc={float(bd['goals_conceded']):.2f}  sv={float(bd['saves']):.2f}  "
                f"defc={float(bd['defensive_contrib']):.2f}  "
                f"card={float(bd['cards']):.2f}  "
                f"bonus={float(bd['bonus']):.2f}"
            )
            tl = float(bd["team_lambda"])
            ol = float(bd["opp_lambda"])
            pc = float(bd["p_clean_sheet"])
            mw = float(bd["minutes_w"])
            gs = float(bd["goal_share"])
            ash = float(bd["assist_share"])
            asc = float(bd["assist_scale"])
            typer.echo(
                f"       model:  λ={tl:.2f}  λopp={ol:.2f}  P(cs)={pc:.2f}  "
                f"min_w={mw:.2f}  g_sh={gs:.3f}  a_sh={ash:.3f}  "
                f"a_scale={asc:.3f}"
            )


@model_app.command("probe-player")
def _probe_player(
    player_id: int = typer.Argument(
        ...,
        metavar="PLAYER_ID",
        help="FPL element id (same as in the game / silver players row).",
    ),
    gw: int | None = typer.Option(
        None,
        "--gw",
        help="Gameweek id (default: FPL ``is_next`` from silver ``events``).",
    ),
) -> None:
    """Verbose xP_fpl breakdown for one player in the target GW (full sentences)."""
    try:
        gw_id, row = model_probe_player_mod.run(player_id=player_id, gw=gw)
    except FileNotFoundError as exc:
        typer.echo(f"model probe-player: {exc}", err=True)
        raise typer.Exit(1) from exc
    except LookupError as exc:
        typer.echo(f"model probe-player: {exc}", err=True)
        raise typer.Exit(1) from exc

    for line in model_probe_player_mod.verbose_breakdown_lines(gw_id, row):
        typer.echo(line)


@model_app.command("season-totals")
def _season_totals() -> None:
    """Sum season-to-date goals and assists on silver players (sanity check)."""
    cfg = load_app_config()
    path = cfg.paths.silver / "players.parquet"
    try:
        rows = read_players_rows(path)
    except FileNotFoundError as exc:
        typer.echo(f"model season-totals: {exc}", err=True)
        raise typer.Exit(1) from exc

    t = league_goals_assists_totals(rows)
    r = t.assists_per_goal
    typer.echo(f"model season-totals: {path}")
    typer.echo(f"  sum goals_scored (all elements): {t.goals_scored}")
    typer.echo(f"  sum assists (all elements):      {t.assists}")
    typer.echo(f"  ratio assists / goals:         {r:.4f}")
    typer.echo(
        "  note: element sums are not PL fixture accounting (e.g. OGs). "
        "That ratio is used as assist_scale in xP_fpl "
        "(assist_mass=assist_scale×λ per side, split by assist_share)."
    )

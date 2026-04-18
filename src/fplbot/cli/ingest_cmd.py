"""`fplbot ingest …` subcommands."""

import httpx
import typer
from pydantic import ValidationError

from fplbot.cli.stub_util import run_stub
from fplbot.commands import ingest_fantasy_scout, ingest_fpl
from fplbot.ingest.errors import FplIngestError

ingest_app = typer.Typer(help="Fetch and cache external data.")


@ingest_app.command("fpl")
def ingest_fpl_cli() -> None:
    """Download official FPL JSON into cache/fpl/."""
    try:
        summary = ingest_fpl.run()
    except httpx.HTTPError as exc:
        typer.echo(f"ingest fpl: HTTP error: {exc}", err=True)
        raise typer.Exit(1) from exc
    except FplIngestError as exc:
        typer.echo(f"ingest fpl: {exc}", err=True)
        raise typer.Exit(1) from exc
    except ValidationError as exc:
        typer.echo(f"ingest fpl: invalid FPL payload: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo("ingest fpl: OK")
    typer.echo(f"  run id:     {summary.run_id}")
    typer.echo(f"  cache dir:  {summary.run_dir}")
    typer.echo(f"  manifest:   {summary.manifest_path}")
    typer.echo(f"  silver:     {summary.silver_dir}")
    typer.echo(
        f"  rows:       events={summary.n_events} teams={summary.n_teams} "
        f"players={summary.n_players} fixtures={summary.n_fixtures}"
    )
    typer.echo(f"  ingested:   {summary.ingested_at}")


@ingest_app.command("fantasy-scout")
def ingest_fantasy_scout_cli() -> None:
    """Optional Fantasy Scout ingestion (Phase 6)."""
    run_stub(ingest_fantasy_scout.run)

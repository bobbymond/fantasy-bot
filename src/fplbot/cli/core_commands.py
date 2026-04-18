"""Top-level CLI commands (non-`ingest`)."""

import logging
import os

import httpx
import typer
from dotenv import load_dotenv

from fplbot.cli.stub_util import run_stub
from fplbot.commands import finalize_gw as finalize_gw_mod
from fplbot.commands import record as record_mod
from fplbot.commands import report as report_mod
from fplbot.commands import suggest as suggest_mod
from fplbot.commands import sync_team as sync_team_mod
from fplbot.ingest.errors import TeamSnapshotError


def register(app: typer.Typer) -> None:
    """Attach stub commands to the root Typer app."""

    @app.command("sync-team")
    def _sync_team(
        entry_id: int | None = typer.Option(
            None,
            "--entry-id",
            help="Override ``fpl.entry_id`` from config.yaml.",
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            "-v",
            help="Log each HTTP request URL, redacted headers, and response status.",
        ),
    ) -> None:
        """Authenticated snapshot → my_team.json (Phase 2)."""
        load_dotenv()
        env_log = os.environ.get("FPLBOT_LOG_HTTP", "").lower() in (
            "1",
            "true",
            "yes",
        )
        log_http = verbose or env_log
        if log_http:
            logging.basicConfig(
                level=logging.INFO,
                format="%(message)s",
                force=True,
            )
        try:
            summary = sync_team_mod.run(entry_id=entry_id, log_requests=log_http)
        except httpx.HTTPError as exc:
            typer.echo(f"sync-team: HTTP error: {exc}", err=True)
            raise typer.Exit(1) from exc
        except TeamSnapshotError as exc:
            typer.echo(f"sync-team: {exc}", err=True)
            raise typer.Exit(1) from exc

        typer.echo("sync-team: OK")
        typer.echo(f"  entry id:   {summary.entry_id}")
        typer.echo(f"  wrote:      {summary.path}")
        typer.echo(f"  picks:      {summary.n_picks}")
        typer.echo(f"  transfers:  {summary.transfer_history_rows} row(s) in history")
        typer.echo(f"  fetched:    {summary.fetched_at}")

    @app.command("suggest")
    def _suggest() -> None:
        """Load caches + team file → report + evaluation run (Phase 4+)."""
        run_stub(suggest_mod.run)

    @app.command("record")
    def _record() -> None:
        """Optional explicit snapshot without full suggest."""
        run_stub(record_mod.run)

    @app.command("finalize-gw")
    def _finalize_gw(
        gameweek: int = typer.Argument(..., metavar="GW", help="Gameweek id."),
    ) -> None:
        """Pull post-GW actuals into evaluation tables."""
        run_stub(finalize_gw_mod.run, gameweek)

    @app.command("report")
    def _report() -> None:
        """Render Markdown/HTML from last run or a run_id."""
        run_stub(report_mod.run)

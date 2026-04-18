"""Typer entrypoint for `fplbot`."""

import typer

from fplbot import __version__
from fplbot.cli.core_commands import register as register_core_commands
from fplbot.cli.ingest_cmd import ingest_app
from fplbot.cli.model_cmd import model_app

app = typer.Typer(
    name="fplbot",
    help="Fantasy Premier League advisory tooling (local; no auto-submit).",
    no_args_is_help=True,
    # Required so `fplbot --version` runs the callback without a subcommand.
    invoke_without_command=True,
)


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Print version and exit.",
        is_eager=True,
    ),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit(0)


app.add_typer(ingest_app, name="ingest")
app.add_typer(model_app, name="model")
register_core_commands(app)

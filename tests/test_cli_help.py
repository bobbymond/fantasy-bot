"""Smoke: package import and CLI --help."""

import importlib

from typer.testing import CliRunner

from fplbot.cli.main import app


def test_import_package() -> None:
    mod = importlib.import_module("fplbot")
    assert hasattr(mod, "__version__")


def test_cli_help_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Fantasy Premier League" in result.stdout


def test_model_probe_help_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["model", "probe", "--help"])
    assert result.exit_code == 0
    assert "gameweek" in result.stdout.lower()


def test_model_fixtures_help_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["model", "fixtures", "--help"])
    assert result.exit_code == 0
    assert "unfinished" in result.stdout.lower()


def test_model_fixture_help_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["model", "fixture", "--help"])
    assert result.exit_code == 0
    assert "fixture" in result.stdout.lower()


def test_cli_version_no_subcommand() -> None:
    """`--version` must work without COMMAND (Typer needs invoke_without_command)."""
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == importlib.import_module("fplbot").__version__

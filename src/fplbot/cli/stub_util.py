"""Helpers for CLI commands that are not implemented yet."""

from collections.abc import Callable
from typing import Any

import typer


def run_stub(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Call ``fn``; on :exc:`NotImplementedError`, echo a hint and exit 1."""
    try:
        fn(*args, **kwargs)
    except NotImplementedError as exc:
        label = str(exc).strip() or fn.__qualname__
        typer.echo(f"{label}: not implemented yet.", err=True)
        raise typer.Exit(1) from exc

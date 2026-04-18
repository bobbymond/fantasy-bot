"""CLI entry for `ingest fpl` — delegates to ingest layer (Phase 1)."""

from fplbot.ingest import fpl as fpl_ingest
from fplbot.ingest.fpl import FplIngestSummary


def run() -> FplIngestSummary:
    """Fetch bootstrap and related endpoints; write under cache/fpl/."""
    return fpl_ingest.run()

"""CLI entry for ``sync-team`` — delegates to ``ingest.team_snapshot``."""

from fplbot.ingest import team_snapshot


def run(
    entry_id: int | None = None,
    *,
    log_requests: bool | None = None,
) -> team_snapshot.TeamSyncSummary:
    """Write normalised ``my_team.json``; never log raw credentials."""
    return team_snapshot.run(entry_id_override=entry_id, log_requests=log_requests)

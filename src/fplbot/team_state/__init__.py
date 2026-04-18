"""Read-only access to squad state (``my_team.json``) for models / CLI."""

from fplbot.team_state.file_source import FileTeamStateSource
from fplbot.team_state.protocol import TeamStateSource
from fplbot.team_state.snapshot_schema import MY_TEAM_SCHEMA_VERSION, MyTeamSnapshotV1

__all__ = [
    "MY_TEAM_SCHEMA_VERSION",
    "FileTeamStateSource",
    "MyTeamSnapshotV1",
    "TeamStateSource",
]

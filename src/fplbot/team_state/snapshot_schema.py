"""Normalised ``my_team.json`` shape (version 1)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MY_TEAM_SCHEMA_VERSION: Literal[1] = 1


class EntrySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    last_deadline_bank: int | None = None
    last_deadline_value: int | None = None
    last_deadline_total_transfers: int | None = None


class PickNorm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element_id: int
    squad_slot: int
    multiplier: int = 1
    is_captain: bool = False
    is_vice_captain: bool = False
    selling_price: int | None = None
    purchase_price: int | None = None


class MyTeamSnapshotV1(BaseModel):
    """Written by ``ingest.team_snapshot``; read by models / suggest."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = MY_TEAM_SCHEMA_VERSION
    fetched_at: str
    entry_id: int
    current_event: int | None = None
    entry: EntrySummary
    transfers_state: dict[str, Any] = Field(default_factory=dict)
    picks: list[PickNorm] = Field(min_length=1)
    transfer_history: list[Any] = Field(default_factory=list)
    active_chip: str | None = None


__all__ = ["MY_TEAM_SCHEMA_VERSION", "EntrySummary", "MyTeamSnapshotV1", "PickNorm"]

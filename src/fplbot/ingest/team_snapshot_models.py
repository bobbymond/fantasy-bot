"""Pydantic models for official **my-team** JSON (tolerant)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiMyTeamPick(BaseModel):
    model_config = ConfigDict(extra="ignore")

    element: int
    position: int
    selling_price: int | None = None
    purchase_price: int | None = None
    multiplier: int = 1
    is_captain: bool = False
    is_vice_captain: bool = False


class ApiMyTeamPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    picks: list[ApiMyTeamPick]
    transfers: dict[str, Any] | None = None
    active_chip: str | None = None


__all__ = ["ApiMyTeamPayload", "ApiMyTeamPick"]

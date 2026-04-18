"""Typing protocols for projection layers (Phase 3)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TeamStrengthSource(Protocol):
    """Per-team home/away attack & defence indices (1 ≈ league average)."""

    def indices(self) -> dict[str, Any]:
        """Return serialisable strength bundle consumed by λ builders."""


@runtime_checkable
class GoalDistributionModel(Protocol):
    """Match-level goal law (v1: independent Poisson marginals)."""

    def clean_sheet_prob(self, goals_conceded_rate: float) -> float:
        """Probability opponent scores 0 given their marginal rate."""


@runtime_checkable
class PlayerInvolvementModel(Protocol):
    """Maps team match context → per-player mean points."""

    def project_players(
        self,
        *,
        players: list[dict[str, Any]],
        fixture: dict[str, Any],
        lambda_home: float,
        lambda_away: float,
        league_mean_forwards: float,
    ) -> list[dict[str, Any]]:
        """Rows with ``player_id``, ``xP_fpl``, and breakdown when applicable."""

"""Partial Pydantic models for official FPL JSON (unknown keys ignored)."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, TypeAdapter

__all__ = [
    "Bootstrap",
    "Element",
    "Event",
    "Fixture",
    "Team",
    "parse_bootstrap",
    "parse_fixtures",
]


def _coerce_optional_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return float(v)
    return float(v)


Floatish = Annotated[float | None, BeforeValidator(_coerce_optional_float)]


class Event(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    deadline_time: str | None = None
    finished: bool = False
    is_current: bool = False
    is_next: bool = False


class Team(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    short_name: str
    code: int


class Element(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    first_name: str
    second_name: str
    web_name: str | None = None
    team: int
    element_type: int
    status: str | None = None
    chance_of_playing_this_round: int | None = None
    chance_of_playing_next_round: int | None = None
    news: str | None = None
    news_added: str | None = None
    now_cost: int
    total_points: int
    goals_scored: int = 0
    assists: int = 0
    minutes: int = 0
    clean_sheets: int = 0
    goals_conceded: int = 0
    bonus: int = 0
    defensive_contribution: int = 0
    defensive_contribution_per_90: Floatish = None
    ep_next: Floatish = None
    expected_goals: Floatish = None
    expected_assists: Floatish = None
    expected_goal_involvements: Floatish = None
    ict_index: Floatish = None


class Bootstrap(BaseModel):
    model_config = ConfigDict(extra="ignore")

    events: list[Event]
    teams: list[Team]
    elements: list[Element]


class Fixture(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    # Unscheduled fixtures use ``null`` in the official JSON.
    event: int | None = None
    team_h: int
    team_a: int
    kickoff_time: str | None = None
    finished: bool = False
    minutes: int | None = None
    team_h_difficulty: int | None = None
    team_a_difficulty: int | None = None
    team_h_score: int | None = None
    team_a_score: int | None = None


_fixture_list_adapter: TypeAdapter[list[Fixture]] = TypeAdapter(list[Fixture])


def parse_bootstrap(data: dict[str, Any]) -> Bootstrap:
    return Bootstrap.model_validate(data)


def parse_fixtures(data: list[object]) -> list[Fixture]:
    return _fixture_list_adapter.validate_python(data)

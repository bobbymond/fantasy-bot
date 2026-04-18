"""2025/26 FPL scoring helpers."""

from __future__ import annotations

import math

from fplbot.models.fpl_scoring_2526 import (
    SEASON_LABEL,
    expected_bonus_points_proxy,
    expected_defensive_contribution_points,
    expected_goals_conceded_points,
    points_per_goal,
)


def test_season_label() -> None:
    assert SEASON_LABEL == "2025-26"


def test_points_per_goal_by_position() -> None:
    assert points_per_goal(1) == 10
    assert points_per_goal(2) == 6
    assert points_per_goal(3) == 5
    assert points_per_goal(4) == 4


def test_expected_conceded_zero_opponent_lambda() -> None:
    assert abs(expected_goals_conceded_points(1e-9)) < 1e-6


def test_expected_bonus_points_proxy_caps_at_three() -> None:
    assert expected_bonus_points_proxy(50.0, 1.0) == 3.0
    assert abs(expected_bonus_points_proxy(2.0, 0.5) - 1.0) < 1e-9


def test_expected_defensive_contribution_points_midfielder() -> None:
    assert expected_defensive_contribution_points(1, 12.0, 1.0) == 0.0
    assert abs(expected_defensive_contribution_points(3, 6.0, 1.0) - 1.0) < 1e-9
    assert expected_defensive_contribution_points(3, 12.0, 1.0) == 2.0
    assert expected_defensive_contribution_points(2, 10.0, 1.0) == 2.0
    assert abs(expected_defensive_contribution_points(2, 5.0, 1.0) - 1.0) < 1e-9


def test_expected_conceded_poisson_mean_two() -> None:
    """λ=2: E[floor(G/2)] = sum_k pmf(k)*floor(k/2)."""
    lam = 2.0
    ev_pairs = 0.0
    for k in range(30):
        ev_pairs += math.exp(-lam) * lam**k / math.factorial(k) * (k // 2)
    expected = -ev_pairs
    assert abs(expected_goals_conceded_points(lam) - expected) < 1e-9

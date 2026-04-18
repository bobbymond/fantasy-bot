"""λ from explicit ratio model (home/away split rates vs μ_home / μ_away)."""

from __future__ import annotations

from fplbot.models.match_lambda import lambda_breakdown, lambdas_for_fixture
from fplbot.models.team_strength import TeamRateTable
from fplbot.settings import ModelParams


def _example_rates() -> TeamRateTable:
    """Textbook numbers (μ_home=1.5, μ_away=1.2, home 1.8/1.0, away 1.1/1.5)."""
    return TeamRateTable(
        mu_home=1.5,
        mu_away=1.2,
        gs_home_avg={1: 1.8, 2: 1.2},
        gc_home_avg={1: 1.0, 2: 1.2},
        gs_away_avg={1: 1.0, 2: 1.1},
        gc_away_avg={1: 1.3, 2: 1.5},
        goals_scored_home={1: 9.0, 2: 6.0},
        goals_conceded_home={1: 5.0, 2: 6.0},
        goals_scored_away={1: 4.0, 2: 4.4},
        goals_conceded_away={1: 5.2, 2: 6.0},
        n_home={1: 5, 2: 5},
        n_away={1: 4, 2: 4},
        window_events=(1,),
        n_fixtures_in_window=1,
        n_finished_gws_silver=1,
    )


def test_lambda_breakdown_matches_lambdas_for_fixture() -> None:
    rates = _example_rates()
    model = ModelParams()
    fx = {"team_h": 1, "team_a": 2}
    d = lambda_breakdown(fx, rates)
    lam_h, lam_a = lambdas_for_fixture(fx, rates, model)
    assert abs(float(d["lambda_home"]) - lam_h) < 1e-9
    assert abs(float(d["lambda_away"]) - lam_a) < 1e-9


def test_lambda_matches_textbook_ratio() -> None:
    rates = _example_rates()
    model = ModelParams()
    fx = {"team_h": 1, "team_a": 2}
    lam_h, lam_a = lambdas_for_fixture(fx, rates, model)
    assert abs(lam_h - 2.25) < 0.001
    assert abs(lam_a - 0.733333) < 0.001


def test_fixture_difficulty_fields_do_not_change_lambda() -> None:
    """FPL difficulty columns may exist on silver rows; λ ignores them."""
    rates = TeamRateTable(
        mu_home=1.5,
        mu_away=1.2,
        gs_home_avg={1: 1.5, 2: 1.5},
        gc_home_avg={1: 1.2, 2: 1.2},
        gs_away_avg={1: 1.2, 2: 1.2},
        gc_away_avg={1: 1.5, 2: 1.5},
        goals_scored_home={1: 0.0, 2: 0.0},
        goals_conceded_home={1: 0.0, 2: 0.0},
        goals_scored_away={1: 0.0, 2: 0.0},
        goals_conceded_away={1: 0.0, 2: 0.0},
        n_home={1: 0, 2: 0},
        n_away={1: 0, 2: 0},
        window_events=(1,),
        n_fixtures_in_window=1,
        n_finished_gws_silver=1,
    )
    model = ModelParams()
    fx_a = {"team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 5}
    fx_b = {"team_h": 1, "team_a": 2, "team_h_difficulty": 5, "team_a_difficulty": 2}
    assert lambdas_for_fixture(fx_a, rates, model) == lambdas_for_fixture(
        fx_b, rates, model
    )

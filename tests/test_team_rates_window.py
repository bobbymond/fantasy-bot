"""Rolling GW window vs full-season (all GWs in silver)."""

from __future__ import annotations

from fplbot.models.team_strength import (
    build_team_rates,
    league_means_all_finished,
    venue_totals_all_finished,
)
from fplbot.settings import ModelParams


def _fx(ev: int, h: int, a: int, hs: int, aws: int) -> dict[str, object]:
    return {
        "id": ev * 100 + h,
        "event": ev,
        "team_h": h,
        "team_a": a,
        "finished": True,
        "team_h_score": hs,
        "team_a_score": aws,
    }


def test_strength_window_zero_uses_all_gameweeks() -> None:
    """GW 1 is high-scoring; GW 2 low. Excluding GW 1 changes μ when window < all."""
    fixtures = [
        _fx(1, 1, 2, 4, 4),
        _fx(2, 1, 2, 0, 0),
    ]
    team_ids = [1, 2]
    all_rates = build_team_rates(fixtures, team_ids, ModelParams(strength_window_gw=0))
    last1 = build_team_rates(fixtures, team_ids, ModelParams(strength_window_gw=1))
    assert all_rates.window_events == (1, 2)
    assert last1.window_events == (2,)
    assert all_rates.mu_home > last1.mu_home
    assert all_rates.n_fixtures_in_window == 2
    assert last1.n_fixtures_in_window == 1
    assert all_rates.n_finished_gws_silver == 2
    assert last1.n_finished_gws_silver == 2
    assert all_rates.goals_scored_home[1] == 4.0
    assert all_rates.n_home[1] == 2
    assert all_rates.goals_conceded_home[1] == 4.0


def test_league_means_and_venue_totals_all_finished() -> None:
    fixtures = [
        _fx(1, 1, 2, 4, 4),
        _fx(2, 1, 2, 0, 0),
    ]
    mh, ma, n = league_means_all_finished(fixtures)
    assert n == 2
    assert abs(mh - 2.0) < 1e-9
    assert abs(ma - 2.0) < 1e-9
    t1 = venue_totals_all_finished(fixtures, 1)
    assert t1["n_home"] == 2
    assert t1["goals_scored_home"] == 4.0
    assert t1["goals_conceded_home"] == 4.0

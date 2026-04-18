"""Phase 3: silver → strengths → λ → player xP + GW resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fplbot.commands import model_probe as model_probe_mod
from fplbot.commands import model_probe_player as model_probe_player_mod
from fplbot.ingest.models import parse_bootstrap, parse_fixtures
from fplbot.models.pipeline import project_fixture_scores, project_gw
from fplbot.models.player_points import (
    is_hard_unavailable,
    team_finished_fixture_counts,
)
from fplbot.models.silver_io import resolve_target_gw
from fplbot.models.team_strength import build_team_rates
from fplbot.settings import ModelParams
from fplbot.silver.writer import SILVER_SCHEMA_VERSION, write_silver


def _fixture_json(name: str) -> object:
    p = Path(__file__).resolve().parent / "fixtures" / "fpl" / name
    return json.loads(p.read_text(encoding="utf-8"))


def _write_min_silver(silver_dir: Path) -> None:
    silver_dir.mkdir(parents=True)
    bootstrap = parse_bootstrap(_fixture_json("min_bootstrap.json"))
    fixtures = parse_fixtures(_fixture_json("min_fixtures.json"))
    write_silver(silver_dir, bootstrap, fixtures, fpl_cache_run_id="test-run")


def test_resolve_target_gw_default_is_next() -> None:
    events = [
        {"id": 1, "finished": True, "is_next": False},
        {"id": 3, "finished": False, "is_next": True},
    ]
    assert resolve_target_gw(events, gw_override=None) == 3


def test_resolve_target_gw_override() -> None:
    events = [{"id": 1, "is_next": True}]
    assert resolve_target_gw(events, gw_override=7) == 7


def test_is_hard_unavailable_status_codes() -> None:
    assert is_hard_unavailable({"status": "i"})
    assert is_hard_unavailable({"status": "S"})
    assert not is_hard_unavailable({"status": "a"})
    assert not is_hard_unavailable({"status": "d"})
    assert not is_hard_unavailable({})


def test_team_finished_fixture_counts_min_fixtures() -> None:
    fixtures = parse_fixtures(_fixture_json("min_fixtures.json"))
    rows = [f.model_dump() for f in fixtures]
    c = team_finished_fixture_counts(rows)
    assert c.get(1) == 2 and c.get(2) == 2


def test_team_rate_table_from_min_silver() -> None:
    bootstrap = parse_bootstrap(_fixture_json("min_bootstrap.json"))
    fixtures = parse_fixtures(_fixture_json("min_fixtures.json"))
    team_ids = [int(t.id) for t in bootstrap.teams]
    rates = build_team_rates(
        [f.model_dump() for f in fixtures],
        team_ids,
        ModelParams(),
    )
    assert rates.mu_home > 0
    assert rates.gs_home_avg[1] > 0


def test_project_gw_default_next(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    silver = tmp_path / "data" / "silver"
    _write_min_silver(silver)
    meta = json.loads((silver / "metadata.json").read_text(encoding="utf-8"))
    assert meta["silver_schema_version"] == SILVER_SCHEMA_VERSION

    gw_id, rows = project_gw(silver, ModelParams())
    assert gw_id == 3
    assert len(rows) == 3
    inj = next(r for r in rows if r.player_id == 3)
    assert inj.xP_fpl == 0.0 and inj.breakdown.minutes_w == 0.0
    assert sum(1 for r in rows if r.xP_fpl > 0) == 2
    assert rows[0].xP_fpl >= rows[-1].xP_fpl
    gk = next(r for r in rows if r.player_id == 1)
    assert gk.team_short == "NOR" and gk.opp_short == "SOU"
    bd = gk.breakdown
    assert abs(
        bd.appearance
        + bd.goals
        + bd.assists
        + bd.clean_sheet
        + bd.goals_conceded
        + bd.saves
        + bd.defensive_contrib
        + bd.cards
        + bd.bonus
        - gk.xP_fpl
    ) < 1e-9
    assert bd.p_clean_sheet >= 0.0
    # min_bootstrap: 2+1 goals, 1 assist → 1/3
    assert abs(bd.assist_scale - (1.0 / 3.0)) < 1e-9
    # bonus: 18 in 180 min → 9 per 90; min_fixtures: 2 finished each team →
    # minutes_w = 180/(90*2) = 1.0 → min(3, 9) = 3
    assert abs(bd.bonus - 3.0) < 1e-9
    assert bd.defensive_contrib == 0.0

    fwd = next(r for r in rows if r.player_id == 2)
    ms = 180.0 / (90.0 * 2.0)  # two finished fixtures for team 1 in min_fixtures
    assert abs(
        fwd.breakdown.defensive_contrib - (2.0 * (10.0 * ms) / 12.0)
    ) < 1e-9


def test_project_fixture_scores_upcoming_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    silver = tmp_path / "data" / "silver"
    _write_min_silver(silver)
    gw_id, rows, sm = project_fixture_scores(silver, ModelParams())
    assert gw_id == 3
    assert len(rows) == 1
    assert sm.n_fixtures_in_window >= 1
    assert sm.n_finished_gws_silver >= sm.n_distinct_gws_in_window
    r = rows[0]
    assert r.fixture_id == 1003
    assert r.expected_home_goals > 0
    assert r.mode_scoreline_prob > 0
    assert abs(r.prob_home_win + r.prob_draw + r.prob_away_win - 1.0) < 1e-9


def test_model_probe_position_and_team_filters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    silver = tmp_path / "data" / "silver"
    _write_min_silver(silver)
    gw_id, rows = model_probe_mod.run(gw=3, top=10, position="gk", team="nor")
    assert gw_id == 3
    assert len(rows) == 1
    assert int(rows[0]["player_id"]) == 1
    assert rows[0]["position"] == "GK"


def test_model_probe_team_id_filter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    silver = tmp_path / "data" / "silver"
    _write_min_silver(silver)
    _, rows = model_probe_mod.run(gw=3, top=10, team="1")
    assert len(rows) == 2
    assert all(int(r["team_id"]) == 1 for r in rows)


def test_model_probe_invalid_position_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    silver = tmp_path / "data" / "silver"
    _write_min_silver(silver)
    with pytest.raises(ValueError, match="invalid position"):
        model_probe_mod.run(gw=3, position="ST")


def test_model_probe_player_verbose_lines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    silver = tmp_path / "data" / "silver"
    _write_min_silver(silver)
    gw_id, row = model_probe_player_mod.run(player_id=1, gw=3)
    assert gw_id == 3
    lines = model_probe_player_mod.verbose_breakdown_lines(gw_id, row)
    text = "\n".join(lines)
    assert "Total model xP_fpl" in text
    assert "Appearance" in text
    assert "Goals conceded" in text
    assert "(GK)" in lines[0]
    assert "  position:               GK" in text
    assert "FPL static from silver" in text
    assert "chance_of_playing_this_round" in text
    assert "Silver probe fixture" in text


def test_model_probe_player_missing_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    silver = tmp_path / "data" / "silver"
    _write_min_silver(silver)
    with pytest.raises(LookupError):
        model_probe_player_mod.run(player_id=99999, gw=3)


def test_project_gw_override_gw1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    silver = tmp_path / "data" / "silver"
    _write_min_silver(silver)
    gw_id, rows = project_gw(silver, ModelParams(), gw=1)
    assert gw_id == 1
    # GW1 finished fixture still yields rows for both squads
    assert len(rows) == 3

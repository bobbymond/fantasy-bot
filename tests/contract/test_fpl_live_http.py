"""Live HTTP contract tests — collected only when ``RUN_LIVE_FPL`` is truthy.

``tests/conftest.py`` ignores this package unless the env var is set, so plain
``pytest`` never hits the network.

Run::

    RUN_LIVE_FPL=1 pytest tests/contract/

Or the full suite including contract::

    RUN_LIVE_FPL=1 pytest
"""

from __future__ import annotations

from fplbot.ingest.client import FplClient
from fplbot.ingest.models import parse_bootstrap, parse_fixtures


def test_live_bootstrap_and_fixtures_parse() -> None:
    """Hit production JSON; assert minimal shape our Phase 1 models expect."""
    with FplClient() as client:
        raw_boot = client.fetch_bootstrap_dict()
        raw_fix = client.fetch_fixtures_list()

    boot = parse_bootstrap(raw_boot)
    assert len(boot.events) >= 1
    assert len(boot.teams) == 20
    assert len(boot.elements) >= 500

    fixtures = parse_fixtures(raw_fix)
    assert len(fixtures) >= 200
    scheduled = [f for f in fixtures if f.event is not None]
    assert len(scheduled) >= 50
    sample = scheduled[0]
    assert sample.team_h >= 1
    assert sample.team_a >= 1

"""Poisson helpers."""

from fplbot.models.poisson_match import match_outcome_probs


def test_match_outcome_probs_sum_to_one() -> None:
    h, d, a = match_outcome_probs(1.8, 1.1)
    assert abs(h + d + a - 1.0) < 1e-9
    assert h > a  # home favourite

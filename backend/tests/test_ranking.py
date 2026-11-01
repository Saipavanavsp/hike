import math
from datetime import UTC, datetime, timedelta

import pytest

from app.services import ranking
from app.services.ranking import Signals, rank_score, recency_decay, top_k

NOW = datetime(2026, 11, 1, tzinfo=UTC)


def test_recency_half_life():
    assert recency_decay(NOW, NOW) == pytest.approx(1.0)
    assert recency_decay(NOW - timedelta(days=14), NOW) == pytest.approx(0.5)
    assert recency_decay(NOW - timedelta(days=28), NOW) == pytest.approx(0.25)


def test_recency_future_dates_clamp_to_one():
    assert recency_decay(NOW + timedelta(days=3), NOW) == pytest.approx(1.0)


def test_text_rank_normalisation_is_bounded():
    assert ranking.normalise_text_rank(0) == 0
    assert ranking.normalise_text_rank(1) == 0.5
    assert 0.99 < ranking.normalise_text_rank(200) < 1
    assert ranking.normalise_text_rank(-3) == 0


def test_all_signals_weighted_sum():
    s = Signals(text=0.5, match=0.8, recency=1.0, category=1.0)
    expected = 0.45 * 0.5 + 0.35 * 0.8 + 0.15 * 1.0 + 0.05 * 1.0
    assert rank_score(s) == pytest.approx(expected)


def test_missing_signals_renormalise_weights():
    # Only recency available -> score equals recency.
    assert rank_score(Signals(None, None, 0.7, None)) == pytest.approx(0.7)
    s = Signals(text=None, match=0.6, recency=0.5, category=None)
    assert rank_score(s) == pytest.approx((0.35 * 0.6 + 0.15 * 0.5) / 0.5)


def test_better_match_outranks_slightly_newer_job():
    old_good = Signals(None, 0.9, recency_decay(NOW - timedelta(days=5), NOW), None)
    new_poor = Signals(None, 0.4, recency_decay(NOW, NOW), None)
    assert rank_score(old_good) > rank_score(new_poor)


def test_top_k_returns_best_first():
    items = [3, 9, 1, 7, 5]
    assert top_k(items, key=lambda x: x, k=3) == [9, 7, 5]
    assert top_k(items, key=lambda x: -x, k=2) == [1, 3]
    assert top_k([], key=lambda x: x, k=3) == []


def test_weights_sum_to_one():
    total = ranking.W_TEXT + ranking.W_MATCH + ranking.W_RECENCY + ranking.W_CATEGORY
    assert math.isclose(total, 1.0)

from __future__ import annotations

import pytest

from app.data import fear_greed, prices

pytestmark = pytest.mark.live


def test_us_history():
    s = prices.fetch_history("AAPL")
    assert len(s) > 1000
    assert s.index.tz is None


def test_korean_resolution():
    assert prices.resolve_symbol("005930", prices.fetch_history) == "005930.KS"


def test_vix_and_index():
    assert not prices.fetch_history("^VIX").empty
    assert not prices.fetch_history("^GSPC").empty


def test_fear_greed():
    data = fear_greed.fetch_fear_greed()
    assert 0 <= data["score"] <= 100
    assert len(data["history"]) > 100

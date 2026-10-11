from __future__ import annotations

import pytest

from app.config import DEFAULT_CONFIG
from app.indicators import fear_greed, market_mdd, vix
from app.indicators.base import NEUTRAL, SIGNAL, STRONG, EvalContext
from tests.helpers import series

IND = DEFAULT_CONFIG["indicators"]


def ctx(cfg, daily=None, fg=None):
    return EvalContext(
        config=cfg,
        get_daily=lambda sym: daily[sym],
        get_fear_greed=lambda: fg,
    )


@pytest.mark.parametrize("value,expected", [(19.9, STRONG), (20, SIGNAL), (24.9, SIGNAL), (25, NEUTRAL)])
def test_fear_greed_grade(value, expected):
    assert fear_greed.grade(value, IND["fear_greed"]) == expected


def test_fear_greed_evaluate():
    fg = {"score": 17.0, "as_of": "2026-10-09", "history": [{"date": "2026-10-09", "value": 17.0}]}
    r = fear_greed.FearGreed().evaluate(ctx(IND["fear_greed"], fg=fg))
    assert r.status == STRONG
    assert r.value == 17.0
    assert r.display == "17"
    assert r.as_of == "2026-10-09"
    assert r.thresholds == [20, 25]
    assert r.label == "극단적 공포"


@pytest.mark.parametrize("value,expected", [(24.9, NEUTRAL), (25, SIGNAL), (29.9, SIGNAL), (30, STRONG)])
def test_vix_grade(value, expected):
    assert vix.grade(value, IND["vix"]) == expected


def test_vix_evaluate():
    r = vix.Vix().evaluate(ctx(IND["vix"], daily={"^VIX": series([15, 20, 32.14])}))
    assert r.status == STRONG
    assert r.display == "32.14"
    assert r.history[-1]["value"] == 32.14


@pytest.mark.parametrize(
    "dd,expected",
    [(-0.1399, NEUTRAL), (-0.14, SIGNAL), (-0.1999, SIGNAL), (-0.20, STRONG), (-0.30, STRONG), (-0.45, STRONG)],
)
def test_mdd_grade(dd, expected):
    assert market_mdd.grade(dd, IND["market_mdd"]) == expected


def test_market_mdd_uses_all_time_high_and_is_not_scored():
    s = series([100, 200, 150, 168])  # 사상 최고 200 대비 -16%
    r = market_mdd.MarketMdd().evaluate(ctx(IND["market_mdd"], daily={"^GSPC": s}))
    assert r.scored is False
    assert r.status == SIGNAL
    assert r.value == pytest.approx(-0.16)
    assert r.display == "-16.0%"
    assert r.history[-1]["value"] == pytest.approx(-16.0)
    assert r.thresholds == [-14.0, -20.0]

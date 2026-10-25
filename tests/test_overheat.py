from __future__ import annotations

import pytest

from app.config import DEFAULT_CONFIG
from app.indicators import overheat
from app.indicators.base import INSUFFICIENT, EvalContext
from tests.helpers import series

CFG = DEFAULT_CONFIG["indicators"]["overheat"]


def ctx(s):
    return EvalContext(config=CFG, get_daily=lambda sym: s, get_fear_greed=dict, symbol="TEST")


@pytest.mark.parametrize("hits, expected", [
    (0, overheat.NORMAL), (1, overheat.NORMAL), (2, overheat.CAUTION), (3, overheat.OVERHEAT), (4, overheat.OVERHEAT),
])
def test_grade_by_count(hits, expected):
    assert overheat.grade(hits, CFG) == expected


def test_spike_meets_all_four_and_warns():
    # 1년 넘게 100에서 머물다 3주 만에 160까지 → 이격도·RSI·3주 상승률·신고가 모두 충족
    s = series([100] * 285 + [100 + 4 * i for i in range(1, 16)])
    r = overheat.Overheat().evaluate(ctx(s))
    assert r.status == overheat.OVERHEAT
    assert r.scored is False
    assert r.warning
    assert r.value == 4
    assert r.display == "4/4"
    assert all(v.startswith("✔") for v in r.details.values())
    assert "200일선" in r.overlays


def test_flat_is_normal():
    r = overheat.Overheat().evaluate(ctx(series([100] * 300)))
    assert r.status == overheat.NORMAL
    assert r.warning is None
    assert r.value == 1   # 횡보하면 52주 최고가 근처 조건만 맞는다
    assert sum(v.startswith("✔") for v in r.details.values()) == 1


def test_far_below_high_with_mild_rise_is_normal():
    s = series([200] * 100 + [100] * 200)
    r = overheat.Overheat().evaluate(ctx(s))
    assert r.status == overheat.NORMAL
    assert r.value == 0


def test_insufficient_history():
    r = overheat.Overheat().evaluate(ctx(series([100] * 150)))
    assert r.status == INSUFFICIENT

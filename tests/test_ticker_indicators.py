from __future__ import annotations

import pytest

from app.config import DEFAULT_CONFIG
from app.indicators import mdd, moving_average, rsi
from app.indicators.base import INSUFFICIENT, NEUTRAL, SIGNAL, STRONG, EvalContext
from tests.helpers import series

IND = DEFAULT_CONFIG["indicators"]


def ctx(cfg, s, symbol="TEST"):
    return EvalContext(config=cfg, get_daily=lambda sym: s, get_fear_greed=dict, symbol=symbol)


# --- RSI ---------------------------------------------------------------

def test_wilder_rsi_extremes():
    up = rsi.wilder_rsi(series(range(1, 60)), 14)
    down = rsi.wilder_rsi(series(range(60, 1, -1)), 14)
    assert up.iloc[-1] == pytest.approx(100.0)
    assert down.iloc[-1] == pytest.approx(0.0)


def test_wilder_rsi_balanced_is_50():
    values = [100 + (i % 2) for i in range(200)]
    assert rsi.wilder_rsi(series(values), 14).iloc[-1] == pytest.approx(50.0, abs=2.0)


@pytest.mark.parametrize(
    "daily,weekly,expected",
    [(30, 35, STRONG), (30, 35.1, SIGNAL), (30.1, 35, SIGNAL), (30.1, 35.1, NEUTRAL), (25, None, SIGNAL), (31, None, NEUTRAL)],
)
def test_rsi_grade(daily, weekly, expected):
    assert rsi.grade(daily, weekly, IND["rsi"]) == expected


def test_rsi_evaluate_both_oversold_is_strong():
    s = series(list(range(300, 100, -1)))  # 200거래일 하락 → 일봉·주봉 모두 0 근처
    r = rsi.Rsi().evaluate(ctx(IND["rsi"], s))
    assert r.status == STRONG
    assert r.details["일봉 RSI(14)"].endswith("(해당)")
    assert r.details["주봉 RSI(14)"].endswith("(해당)")
    assert r.thresholds == [30, 35]
    assert "주봉 RSI" in r.overlays


def test_rsi_evaluate_only_weekly_oversold_is_signal():
    s = series(list(range(300, 100, -1)) + [103, 106, 109, 112, 115])  # 긴 하락 후 5일 반등
    r = rsi.Rsi().evaluate(ctx(IND["rsi"], s))
    assert r.details["일봉 RSI(14)"].endswith("(미해당)")
    assert r.details["주봉 RSI(14)"].endswith("(해당)")
    assert r.status == SIGNAL


def test_rsi_weekly_insufficient_uses_daily_only():
    s = series(list(range(100, 60, -1)))  # 40거래일 = 약 8주, 주봉 RSI 계산 불가
    r = rsi.Rsi().evaluate(ctx(IND["rsi"], s))
    assert r.details["주봉 RSI(14)"] == "데이터 부족"
    assert r.status == SIGNAL


def test_rsi_insufficient_data():
    r = rsi.Rsi().evaluate(ctx(IND["rsi"], series([1, 2, 3, 4, 5])))
    assert r.status == INSUFFICIENT


# --- 종목 MDD (52주) ----------------------------------------------------

def test_ticker_mdd_uses_52_week_high_not_all_time_high():
    values = [200] * 50 + [100] * 300 + [85]  # 사상 최고 200, 최근 252일 최고 100
    r = mdd.Mdd().evaluate(ctx(IND["mdd"], series(values)))
    assert r.scored is True
    assert r.value == pytest.approx(-0.15)
    assert r.status == SIGNAL
    assert r.details["사상 최고가 대비"] == "-57.5%"
    assert r.thresholds == [-14.0, -20.0]


def test_ticker_mdd_short_history_uses_available_high():
    r = mdd.Mdd().evaluate(ctx(IND["mdd"], series([100, 120, 90])))
    assert r.value == pytest.approx(-0.25)
    assert r.status == STRONG


# --- 이동평균 -----------------------------------------------------------

@pytest.mark.parametrize("gap,expected", [(0.0, NEUTRAL), (0.02, NEUTRAL), (-0.001, SIGNAL), (-0.049, SIGNAL), (-0.05, STRONG), (-0.2, STRONG)])
def test_grade_gap(gap, expected):
    assert moving_average.grade_gap(gap, IND["moving_average"]) == expected


def test_ma_both_available_signal():
    s = series([100] * 1100 + [97])  # 200일·200주 모두 약 -3%
    r = moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s))
    assert r.status == SIGNAL
    assert r.details["200일 이격도"].startswith("-3.0%")
    assert r.details["200주 이격도"].startswith("-3.0%")
    assert set(r.overlays) == {"200일선", "200주선"}


def test_ma_strong_when_5pct_below():
    s = series([100] * 1100 + [90])
    assert moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s)).status == STRONG


def test_ma_takes_strongest_of_daily_and_weekly():
    # 오래 200 → 최근 300일 100: 200일선 약 100(이격 -2%), 200주선은 100보다 훨씬 위(이격 -5% 이하)
    s = series([200] * 900 + [100] * 300 + [98])
    r = moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s))
    assert r.details["200일 이격도"].endswith("(신호)")
    assert r.details["200주 이격도"].endswith("(강한 신호)")
    assert r.status == STRONG


def test_ma_above_both_neutral():
    s = series([100] * 1100 + [110])
    assert moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s)).status == NEUTRAL


def test_ma_weekly_insufficient_uses_daily_only():
    s = series([100] * 300 + [97])
    r = moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s))
    assert r.status == SIGNAL
    assert r.details["200주 이격도"] == "데이터 부족"
    assert set(r.overlays) == {"200일선"}


def test_ma_daily_insufficient():
    r = moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], series([100] * 150)))
    assert r.status == INSUFFICIENT

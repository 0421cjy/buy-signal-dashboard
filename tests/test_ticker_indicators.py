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


# --- 이동평균: 200일·200주 중 이탈 개수 ------------------------------

@pytest.mark.parametrize(
    "daily,weekly,expected",
    [(-0.01, -0.01, STRONG), (-0.01, 0.02, SIGNAL), (0.0, -0.3, SIGNAL), (0.0, 0.0, NEUTRAL), (-0.2, None, SIGNAL), (0.1, None, NEUTRAL)],
)
def test_ma_grade_counts_lines_below(daily, weekly, expected):
    assert moving_average.grade(daily, weekly) == expected


def test_ma_both_below_is_strong():
    s = series([100] * 1100 + [97])  # 200일·200주 모두 약 -3%
    r = moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s))
    assert r.status == STRONG
    assert r.details["200일 이격도"] == "-3.0% (이탈)"
    assert r.details["200주 이격도"] == "-3.0% (이탈)"
    assert set(r.overlays) == {"200일선", "200주선"}


def test_ma_only_daily_below_is_signal():
    up = [50 + i * 100 / 1099 for i in range(1100)]  # 장기 상승 → 200주선은 한참 아래
    r = moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], series(up + [140])))
    assert r.details["200일 이격도"].endswith("(이탈)")
    assert r.details["200주 이격도"].endswith("(위)")
    assert r.status == SIGNAL


def test_ma_only_weekly_below_is_signal():
    s = series([200] * 900 + [100] * 300 + [110])  # 200일선(약 100) 위, 200주선(약 170) 아래
    r = moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s))
    assert r.details["200일 이격도"].endswith("(위)")
    assert r.details["200주 이격도"].endswith("(이탈)")
    assert r.status == SIGNAL


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


# --- 주봉 라벨: 진행 중인 주는 실제 마지막 거래일로 ----------------------

def test_to_weekly_labels_with_actual_last_trading_day():
    s = series(range(1, 13))  # 2020-01-01(수) ~ 2020-01-16(목)
    weekly = moving_average.to_weekly(s)
    assert weekly.index[-1] == s.index[-1]
    assert weekly.iloc[-1] == 12.0
    assert list(weekly.index.strftime("%Y-%m-%d")) == ["2020-01-03", "2020-01-10", "2020-01-16"]


def test_weekly_rsi_overlay_matches_card_midweek():
    s = series(list(range(300, 100, -1)) + [103, 106, 109, 112, 115])  # 마지막 날이 화요일
    assert s.index[-1].weekday() != 4
    r = rsi.Rsi().evaluate(ctx(IND["rsi"], s))
    card_value = float(r.details["주봉 RSI(14)"].split()[0])
    assert round(r.overlays["주봉 RSI"][-1]["value"], 1) == card_value

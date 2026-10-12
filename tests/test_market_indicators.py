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
    assert r.display == "17.0"
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


LV = market_mdd.levels(IND["market_mdd"])


@pytest.mark.parametrize(
    "dd,expected",
    [(-0.1399, NEUTRAL), (-0.14, SIGNAL), (-0.2999, SIGNAL), (-0.30, STRONG), (-0.47, STRONG), (-0.6, STRONG)],
)
def test_mdd_grade(dd, expected):
    assert market_mdd.grade(dd, LV) == expected


@pytest.mark.parametrize("dd,expected", [(-0.4699, False), (-0.47, True), (-0.6, True)])
def test_mdd_extreme(dd, expected):
    assert market_mdd.is_extreme(dd, LV) is expected


def test_market_mdd_uses_all_time_high_and_is_not_scored():
    s = series([100, 200, 150, 168])  # 사상 최고 200 대비 -16%
    r = market_mdd.MarketMdd().evaluate(ctx(IND["market_mdd"], daily={"^GSPC": s}))
    assert r.scored is False
    assert r.status == SIGNAL
    assert r.value == pytest.approx(-0.16)
    assert r.display == "-16.0%"
    assert "주식 매수 시작" in r.label
    assert r.warning is None
    assert r.history[-1]["value"] == pytest.approx(-16.0)
    assert r.thresholds == [-14.0, -30.0, -47.0]


def test_market_mdd_extreme_shows_warning():
    r = market_mdd.MarketMdd().evaluate(ctx(IND["market_mdd"], daily={"^GSPC": series([100, 200, 100])}))
    assert r.status == STRONG
    assert "극단적 하락" in r.warning


def test_market_mdd_name_has_no_reference_suffix():
    assert market_mdd.MarketMdd.name == "S&P 500 MDD"


def test_market_mdd_threshold_text_has_decimals():
    r = market_mdd.MarketMdd().evaluate(ctx(IND["market_mdd"], daily={"^GSPC": series([100, 90])}))
    assert r.threshold == "-14.0% 이하 매수 시작 · -30.0% 이하 비중 확대 · -47.0% 이하 극단적 하락"


@pytest.mark.parametrize("level,dd", [(-0.341, 65.9 / 100 - 1), (-0.341, 164.75 / 250 - 1), (-0.161, 83.9 / 100 - 1)])
def test_mdd_boundary_float_noise_still_hits_level(level, dd):
    lv = {"signal": level, "strong": level, "extreme": level}
    assert market_mdd.grade(dd, lv) != NEUTRAL
    assert market_mdd.is_extreme(dd, lv)


# --- QQQ MDD (참고) ----------------------------------------------------------

from app.indicators import qqq_mdd  # noqa: E402


def test_qqq_mdd_starts_at_minus_20_with_same_remaining_price_ratio():
    s = series([100, 200, 150])   # 사상 최고 200 대비 -25%
    r = qqq_mdd.QqqMdd().evaluate(ctx(IND["qqq_mdd"], daily={"QQQ": s}))
    assert r.name == "QQQ MDD"
    assert r.scored is False
    assert r.value == pytest.approx(-0.25)
    assert r.status == SIGNAL
    assert r.thresholds == pytest.approx([-20.0, -41.0042, -60.9101], abs=1e-3)
    assert r.threshold == "-20.0% 이하 매수 시작 · -41.0% 이하 비중 확대 · -60.9% 이하 극단적 하락"
    assert r.warning is None


@pytest.mark.parametrize("last,expected", [(161, NEUTRAL), (160, SIGNAL), (118, SIGNAL), (117, STRONG)])
def test_qqq_mdd_boundaries(last, expected):
    r = qqq_mdd.QqqMdd().evaluate(ctx(IND["qqq_mdd"], daily={"QQQ": series([100, 200, last])}))
    assert r.status == expected


def test_qqq_mdd_extreme_warning():
    r = qqq_mdd.QqqMdd().evaluate(ctx(IND["qqq_mdd"], daily={"QQQ": series([100, 200, 70])}))
    assert r.status == STRONG
    assert "극단적 하락" in r.warning


def _qqq_years(annual, current_values):
    """해마다 100에서 시작해 후반에 dd만큼 떨어지는 일봉 + 올해 값."""
    import pandas as pd

    blocks = []
    for i, dd in enumerate(annual):
        idx = pd.bdate_range(f"{2020 + i}-01-01", f"{2020 + i}-12-31")
        half = len(idx) // 2
        blocks.append(pd.Series([100.0] * half + [100.0 * (1 + dd)] * (len(idx) - half), index=idx))
    idx = pd.bdate_range(f"{2020 + len(annual)}-01-01", periods=len(current_values))
    blocks.append(pd.Series([float(v) for v in current_values], index=idx))
    return pd.concat(blocks)


def test_qqq_mdd_first_signal_is_actual_average_annual_drawdown():
    s = _qqq_years([-0.3, -0.2, -0.4], [100, 65])      # 연평균 -30%, 지금 -35%
    r = qqq_mdd.QqqMdd().evaluate(ctx(IND["qqq_mdd"], daily={"QQQ": s}))
    assert r.thresholds[0] == pytest.approx(-30.0)
    assert r.thresholds[1] == pytest.approx(-56.98, abs=0.05)
    assert r.thresholds[2] == pytest.approx(-77.72, abs=0.05)
    assert r.status == SIGNAL
    assert r.details["연평균 최대 하락률"] == "-30.0% (3년)"


def test_qqq_mdd_short_history_uses_default_anchor():
    r = qqq_mdd.QqqMdd().evaluate(ctx(IND["qqq_mdd"], daily={"QQQ": series([100, 200, 150])}))
    assert r.thresholds[0] == pytest.approx(-20.0)
    assert "기본값" in r.details["연평균 최대 하락률"]

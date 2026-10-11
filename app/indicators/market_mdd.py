from __future__ import annotations

import math
from typing import Dict, List, Optional

from app.indicators.base import (
    NEUTRAL, SIGNAL, STRONG, EvalContext, Indicator, IndicatorResult, as_of, fmt_pct, register, to_points,
)

LABELS = {
    STRONG: "헷지 자산 추가 매도 → 비중 확대",
    SIGNAL: "헷지 자산 일부 매도 → 주식 매수 시작",
    NEUTRAL: "대기",
}
EXTREME_WARNING = "⚠ 극단적 하락 구간입니다"
_PRECISION = 9  # 65.9/100-1 = -0.34099999… 같은 부동소수점 오차로 경계값이 빗나가지 않게 반올림해 비교


def levels(cfg: dict, anchor: Optional[float] = None) -> Dict[str, float]:
    """매수 시작·비중 확대·극단적 하락 구간.

    anchor(종목 연평균 최대 하락률)가 있으면 매수 시작을 anchor로 두고, 나머지 두 구간은
    기본 구간의 '남은 가격' 비율을 그대로 적용한다. 기본값이면 86% → 70% → 53%이므로
    70% = 86%^2.37, 53% = 86%^4.21 이고, 종목에는 (1 + anchor)를 같은 횟수만큼 거듭제곱한다.
    결과는 -100%에 닿지 않고, anchor가 기본 매수 시작값이면 기본 구간과 정확히 같다."""
    signal = cfg["signal_at_or_below"]
    strong = cfg["strong_at_or_below"]
    extreme = cfg["extreme_at_or_below"]
    if anchor is None:
        return {"signal": signal, "strong": strong, "extreme": extreme}
    base = math.log(1 + signal)
    remaining = 1 + anchor
    return {
        "signal": anchor,
        "strong": remaining ** (math.log(1 + strong) / base) - 1,
        "extreme": remaining ** (math.log(1 + extreme) / base) - 1,
    }


def _at_or_below(drawdown: float, level: float) -> bool:
    return round(drawdown, _PRECISION) <= round(level, _PRECISION)


def grade(drawdown: float, lv: Dict[str, float]) -> str:
    if _at_or_below(drawdown, lv["strong"]):
        return STRONG
    if _at_or_below(drawdown, lv["signal"]):
        return SIGNAL
    return NEUTRAL


def is_extreme(drawdown: float, lv: Dict[str, float]) -> bool:
    return _at_or_below(drawdown, lv["extreme"])


def threshold_text(lv: Dict[str, float]) -> str:
    return (
        f"{lv['signal'] * 100:.1f}% 이하 매수 시작 · "
        f"{lv['strong'] * 100:.1f}% 이하 비중 확대 · "
        f"{lv['extreme'] * 100:.1f}% 이하 극단적 하락"
    )


def threshold_lines(lv: Dict[str, float]) -> List[float]:
    return [round(lv[k] * 100, 4) for k in ("signal", "strong", "extreme")]


@register
class MarketMdd(Indicator):
    id = "market_mdd"
    name = "S&P 500 MDD"
    scope = "market"
    scored = False
    order = 30

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        s = ctx.get_daily(cfg["index"]).dropna()
        if s.empty:
            return self.insufficient("지수 데이터가 없습니다")
        drawdown = s / s.cummax() - 1
        value = float(drawdown.iloc[-1])
        lv = levels(cfg)
        status = grade(value, lv)
        return self.make(
            status=status,
            value=value,
            display=fmt_pct(value),
            label=f"사상 최고가 대비 · {LABELS[status]}",
            threshold=threshold_text(lv),
            as_of=as_of(s),
            history=to_points(drawdown, scale=100),
            thresholds=threshold_lines(lv),
            warning=EXTREME_WARNING if is_extreme(value, lv) else None,
        )

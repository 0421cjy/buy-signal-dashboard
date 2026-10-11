from __future__ import annotations

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
    anchor(종목 연평균 최대 하락률)가 있으면 매수 시작을 anchor로 옮기고,
    나머지 두 구간은 기본값의 간격(-16%p, -33%p)을 그대로 유지한다."""
    signal = cfg["signal_at_or_below"]
    shift = 0.0 if anchor is None else anchor - signal
    return {
        "signal": signal + shift,
        "strong": cfg["strong_at_or_below"] + shift,
        "extreme": cfg["extreme_at_or_below"] + shift,
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

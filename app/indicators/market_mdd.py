from __future__ import annotations

from typing import Dict, List

from app.indicators.base import (
    NEUTRAL, SIGNAL, STRONG, EvalContext, Indicator, IndicatorResult, as_of, fmt_pct, register, to_points,
)

LABELS = {
    STRONG: "헷지 자산 추가 매도 → 비중 확대",
    SIGNAL: "헷지 자산 일부 매도 → 주식 매수 시작",
    NEUTRAL: "대기",
}
EXTREME_WARNING = "⚠ 극단적 하락 구간입니다"


def levels(cfg: dict, scale: float = 1.0) -> Dict[str, float]:
    """매수 시작·비중 확대·극단적 하락 구간. scale로 종목 특성에 맞게 늘이거나 줄인다."""
    return {
        "signal": cfg["signal_at_or_below"] * scale,
        "strong": cfg["strong_at_or_below"] * scale,
        "extreme": cfg["extreme_at_or_below"] * scale,
    }


def grade(drawdown: float, lv: Dict[str, float]) -> str:
    if drawdown <= lv["strong"]:
        return STRONG
    if drawdown <= lv["signal"]:
        return SIGNAL
    return NEUTRAL


def is_extreme(drawdown: float, lv: Dict[str, float]) -> bool:
    return drawdown <= lv["extreme"]


def threshold_text(lv: Dict[str, float]) -> str:
    return (
        f"{lv['signal'] * 100:.0f}% 이하 매수 시작 · "
        f"{lv['strong'] * 100:.0f}% 이하 비중 확대 · "
        f"{lv['extreme'] * 100:.0f}% 이하 극단적 하락"
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

from __future__ import annotations

from app.indicators.base import (
    NEUTRAL, SIGNAL, STRONG, EvalContext, Indicator, IndicatorResult, as_of, fmt_pct, register, to_points,
)

LABELS = {STRONG: "비중 대폭 확대 구간", SIGNAL: "매수 시작 구간", NEUTRAL: "대기"}


def grade(drawdown: float, cfg: dict) -> str:
    if drawdown <= cfg["strong_at_or_below"]:
        return STRONG
    if drawdown <= cfg["signal_at_or_below"]:
        return SIGNAL
    return NEUTRAL


def threshold_text(cfg: dict) -> str:
    return (
        f"{cfg['signal_at_or_below'] * 100:.0f}% 이하 매수 시작 · "
        f"{cfg['strong_at_or_below'] * 100:.0f}% 이하 비중 확대"
    )


def threshold_lines(cfg: dict) -> list:
    return [round(cfg["signal_at_or_below"] * 100, 4), round(cfg["strong_at_or_below"] * 100, 4)]


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
        status = grade(value, cfg)
        return self.make(
            status=status,
            value=value,
            display=fmt_pct(value),
            label=f"사상 최고가 대비 · {LABELS[status]}",
            threshold=threshold_text(cfg),
            as_of=as_of(s),
            history=to_points(drawdown, scale=100),
            thresholds=threshold_lines(cfg),
        )

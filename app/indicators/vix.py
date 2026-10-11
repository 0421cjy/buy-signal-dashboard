from __future__ import annotations

from app.indicators.base import (
    NEUTRAL, SIGNAL, STRONG, EvalContext, Indicator, IndicatorResult, as_of, register, to_points,
)

_LABELS = {STRONG: "시장 패닉", SIGNAL: "불안 확대", NEUTRAL: "안정"}


def grade(value: float, cfg: dict) -> str:
    if value >= cfg["strong_at_or_above"]:
        return STRONG
    if value >= cfg["signal_at_or_above"]:
        return SIGNAL
    return NEUTRAL


@register
class Vix(Indicator):
    id = "vix"
    name = "VIX"
    scope = "market"
    order = 20

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        s = ctx.get_daily("^VIX").dropna()
        if s.empty:
            return self.insufficient("VIX 데이터가 없습니다")
        value = float(s.iloc[-1])
        status = grade(value, cfg)
        return self.make(
            status=status,
            value=value,
            display=f"{value:.2f}",
            label=_LABELS[status],
            threshold=f"{cfg['strong_at_or_above']} 이상 강한 신호 · {cfg['signal_at_or_above']} 이상 신호",
            as_of=as_of(s),
            history=to_points(s),
            thresholds=[cfg["strong_at_or_above"], cfg["signal_at_or_above"]],
        )

from __future__ import annotations

from app.indicators.base import NEUTRAL, SIGNAL, STRONG, EvalContext, Indicator, IndicatorResult, register

_LABELS = {STRONG: "극단적 공포", SIGNAL: "공포", NEUTRAL: "공포 구간 아님"}


def grade(value: float, cfg: dict) -> str:
    if value < cfg["strong_below"]:
        return STRONG
    if value < cfg["signal_below"]:
        return SIGNAL
    return NEUTRAL


@register
class FearGreed(Indicator):
    id = "fear_greed"
    name = "공포·탐욕 지수"
    scope = "market"
    order = 10

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        data = ctx.get_fear_greed()
        value = float(data["score"])
        status = grade(value, cfg)
        return self.make(
            status=status,
            value=value,
            display=f"{value:.0f}",
            label=_LABELS[status],
            threshold=f"{cfg['strong_below']} 미만 강한 신호 · {cfg['signal_below']} 미만 신호",
            as_of=data.get("as_of"),
            history=data.get("history", []),
            thresholds=[cfg["strong_below"], cfg["signal_below"]],
        )

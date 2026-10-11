from __future__ import annotations

from app.indicators.base import EvalContext, Indicator, IndicatorResult, as_of, fmt_pct, register, to_points
from app.indicators.market_mdd import LABELS, grade, threshold_lines, threshold_text


@register
class Mdd(Indicator):
    id = "mdd"
    name = "MDD (52주 고점 대비)"
    scope = "ticker"
    order = 50

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        lookback = int(cfg["lookback_days"])
        s = ctx.get_daily(ctx.symbol).dropna()
        if s.empty:
            return self.insufficient("가격 데이터가 없습니다")
        drawdown = s / s.rolling(lookback, min_periods=1).max() - 1
        value = float(drawdown.iloc[-1])
        status = grade(value, cfg)
        ath = float(s.iloc[-1] / s.max() - 1)
        return self.make(
            status=status,
            value=value,
            display=fmt_pct(value),
            label=LABELS[status],
            threshold=threshold_text(cfg),
            as_of=as_of(s),
            details={"사상 최고가 대비": fmt_pct(ath)},
            history=to_points(drawdown, scale=100),
            thresholds=threshold_lines(cfg),
        )

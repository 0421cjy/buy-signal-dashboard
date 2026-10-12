from __future__ import annotations

from app.indicators.base import EvalContext, Indicator, IndicatorResult, as_of, fmt_pct, register, to_points
from app.indicators.market_mdd import EXTREME_WARNING, LABELS, grade, is_extreme, levels, threshold_lines, threshold_text


@register
class QqqMdd(Indicator):
    """QQQ(나스닥100) 사상 최고가 대비 하락률 — 참고용(점수 제외).

    첫 신호는 anchor(기본 -20%)이고, 비중 확대·극단적 하락은 S&P 500 단계(-14/-30/-47)의
    '남은 가격' 비율을 그대로 옮겨 계산한다(-20% → -41.0% / -60.9%).
    """

    id = "qqq_mdd"
    name = "QQQ MDD"
    scope = "market"
    scored = False
    order = 31

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        s = ctx.get_daily(cfg["index"]).dropna()
        if s.empty:
            return self.insufficient("QQQ 데이터가 없습니다")
        drawdown = s / s.cummax() - 1
        value = float(drawdown.iloc[-1])
        lv = levels(cfg, anchor=cfg["anchor"])
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

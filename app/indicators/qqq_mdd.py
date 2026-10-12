from __future__ import annotations

from app.indicators.base import EvalContext, Indicator, IndicatorResult, as_of, fmt_pct, register, to_points
from app.indicators.market_mdd import EXTREME_WARNING, LABELS, grade, is_extreme, levels, threshold_lines, threshold_text
from app.indicators.mdd import annual_max_drawdowns


@register
class QqqMdd(Indicator):
    """QQQ(나스닥100) 사상 최고가 대비 하락률 — 참고용(점수 제외).

    첫 신호는 QQQ의 실제 연평균 최대 하락률(끝난 해마다 그해 최고점 대비 최대 하락률의 평균)이고,
    끝난 해가 min_years 미만이면 anchor(기본 -20%)를 쓴다. 비중 확대·극단적 하락은
    S&P 500 단계(-14/-30/-47)의 '남은 가격' 비율을 첫 신호에 맞춰 옮겨 계산한다.
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

        years = annual_max_drawdowns(s, int(cfg["min_days_per_year"]))
        if len(years) >= int(cfg["min_years"]):
            anchor = float(years.mean())
            basis = f"{fmt_pct(anchor)} ({len(years)}년)"
        else:
            anchor = float(cfg["anchor"])
            basis = f"이력 부족({len(years)}년) · 기본값 {fmt_pct(anchor)} 사용"
        lv = levels(cfg, anchor=anchor)

        drawdown = s / s.cummax() - 1
        value = float(drawdown.iloc[-1])
        status = grade(value, lv)
        return self.make(
            status=status,
            value=value,
            display=fmt_pct(value),
            label=f"사상 최고가 대비 · {LABELS[status]}",
            threshold=threshold_text(lv),
            as_of=as_of(s),
            details={"연평균 최대 하락률": basis},
            history=to_points(drawdown, scale=100),
            thresholds=threshold_lines(lv),
            warning=EXTREME_WARNING if is_extreme(value, lv) else None,
        )

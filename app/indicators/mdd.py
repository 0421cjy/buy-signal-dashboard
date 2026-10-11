from __future__ import annotations

import pandas as pd

from app.indicators.base import EvalContext, Indicator, IndicatorResult, as_of, fmt_pct, register, to_points
from app.indicators.market_mdd import (
    EXTREME_WARNING, LABELS, grade, is_extreme, levels, threshold_lines, threshold_text,
)


def ytd_drawdown(s: pd.Series) -> pd.Series:
    """해마다 새로 시작하는, 그해 최고 종가 대비 하락률."""
    return s / s.groupby(s.index.year).cummax() - 1


def annual_max_drawdowns(s: pd.Series, min_days: int) -> pd.Series:
    """끝난 해별 연중 최대 하락률. 올해와 거래일이 min_days 미만인 해는 뺀다."""
    dd = ytd_drawdown(s)
    by_year = dd.groupby(dd.index.year)
    worst = by_year.min()[by_year.size() >= min_days]
    return worst[worst.index != s.index[-1].year]


@register
class Mdd(Indicator):
    id = "mdd"
    name = "MDD (올해 고점 대비)"
    scope = "ticker"
    order = 50

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        s = ctx.get_daily(ctx.symbol).dropna()
        if s.empty:
            return self.insufficient("가격 데이터가 없습니다")

        years = annual_max_drawdowns(s, int(cfg["min_days_per_year"]))
        if len(years) >= int(cfg["min_years"]):
            average = float(years.mean())
            scale = average / cfg["base_average"]
            basis = f"{fmt_pct(average)} ({len(years)}년)"
        else:
            scale = 1.0
            basis = f"이력 부족({len(years)}년) · 기본 기준 사용"
        lv = levels(cfg, scale)

        drawdown = ytd_drawdown(s)
        value = float(drawdown.iloc[-1])
        status = grade(value, lv)
        last_year = s.iloc[-252:]
        return self.make(
            status=status,
            value=value,
            display=fmt_pct(value),
            label=LABELS[status],
            threshold=threshold_text(lv),
            as_of=as_of(s),
            details={
                "연평균 최대 하락률": basis,
                "52주 고점 대비": fmt_pct(float(s.iloc[-1] / last_year.max() - 1)),
                "사상 최고가 대비": fmt_pct(float(s.iloc[-1] / s.max() - 1)),
            },
            history=to_points(drawdown, scale=100),
            thresholds=threshold_lines(lv),
            warning=EXTREME_WARNING if is_extreme(value, lv) else None,
        )

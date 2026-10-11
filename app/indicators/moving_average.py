from __future__ import annotations

from typing import Optional

import pandas as pd

from app.indicators.base import (
    NEUTRAL, SIGNAL, STRONG, EvalContext, Indicator, IndicatorResult, as_of, fmt_pct, register, to_points,
)

_LABELS = {STRONG: "200일선·200주선 모두 아래", SIGNAL: "200일선·200주선 중 하나 아래", NEUTRAL: "장기 이평선 위"}


def to_weekly(s: pd.Series) -> pd.Series:
    """주(월~금)마다 마지막 거래일 종가. 인덱스는 그 실제 거래일이라
    진행 중인 주나 금요일 휴장 주도 일봉과 날짜가 맞는다."""
    s = s.dropna()
    week = s.index.to_period("W-FRI")
    last_of_week = ~pd.Series(week).duplicated(keep="last").to_numpy()
    return s[last_of_week]


def grade(daily_gap: float, weekly_gap: Optional[float]) -> str:
    """이평선 아래로 내려간 개수: 1개면 신호, 2개면 강한 신호."""
    below = int(daily_gap < 0) + int(weekly_gap is not None and weekly_gap < 0)
    if below == 2:
        return STRONG
    if below == 1:
        return SIGNAL
    return NEUTRAL


def _mark(gap: float) -> str:
    return f"{fmt_pct(gap)} ({'이탈' if gap < 0 else '위'})"


def _gap(price: float, sma: pd.Series) -> Optional[float]:
    last = sma.dropna()
    if last.empty:
        return None
    return price / float(last.iloc[-1]) - 1


@register
class MovingAverage(Indicator):
    id = "moving_average"
    name = "200일 / 200주 이동평균"
    scope = "ticker"
    order = 60

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        dw, ww = int(cfg["daily_window"]), int(cfg["weekly_window"])
        s = ctx.get_daily(ctx.symbol).dropna()
        if len(s) < dw:
            return self.insufficient(f"{dw}일 이동평균 계산에 데이터가 부족합니다")
        price = float(s.iloc[-1])
        daily_sma = s.rolling(dw).mean()
        weekly = to_weekly(s)
        weekly_sma = weekly.rolling(ww).mean() if len(weekly) >= ww else None

        gap_d = _gap(price, daily_sma)
        gap_w = _gap(price, weekly_sma) if weekly_sma is not None else None
        details = {f"{dw}일 이격도": _mark(gap_d), f"{ww}주 이격도": _mark(gap_w) if gap_w is not None else "데이터 부족"}
        overlays = {f"{dw}일선": to_points(daily_sma)}
        if weekly_sma is not None:
            overlays[f"{ww}주선"] = to_points(weekly_sma.reindex(s.index, method="ffill"))

        status = grade(gap_d, gap_w)
        return self.make(
            status=status,
            value=gap_d,
            display=fmt_pct(gap_d),
            label=_LABELS[status],
            threshold=f"{dw}일선·{ww}주선 중 하나 아래 신호 · 둘 다 아래 강한 신호",
            as_of=as_of(s),
            details=details,
            history=to_points(s),
            overlays=overlays,
        )

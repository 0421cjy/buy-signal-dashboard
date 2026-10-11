from __future__ import annotations

from typing import Optional

import pandas as pd

from app.indicators.base import (
    NEUTRAL, SIGNAL, STATUS_TEXT, STRONG, EvalContext, Indicator, IndicatorResult,
    as_of, fmt_pct, register, strongest, to_points,
)

_LABELS = {STRONG: "장기 이평선 아래로 크게 이탈", SIGNAL: "장기 이평선 아래", NEUTRAL: "장기 이평선 위"}


def to_weekly(s: pd.Series) -> pd.Series:
    return s.resample("W-FRI").last().dropna()


def grade_gap(gap: float, cfg: dict) -> str:
    if gap <= cfg["strong_gap_at_or_below"]:
        return STRONG
    if gap < 0:
        return SIGNAL
    return NEUTRAL


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
        status_d = grade_gap(gap_d, cfg)
        details = {f"{dw}일 이격도": f"{fmt_pct(gap_d)} ({STATUS_TEXT[status_d]})"}
        overlays = {f"{dw}일선": to_points(daily_sma)}
        statuses = [status_d]

        if weekly_sma is not None:
            gap_w = _gap(price, weekly_sma)
            status_w = grade_gap(gap_w, cfg)
            statuses.append(status_w)
            details[f"{ww}주 이격도"] = f"{fmt_pct(gap_w)} ({STATUS_TEXT[status_w]})"
            overlays[f"{ww}주선"] = to_points(weekly_sma.reindex(s.index, method="ffill"))
        else:
            details[f"{ww}주 이격도"] = "데이터 부족"

        status = strongest(*statuses)
        return self.make(
            status=status,
            value=gap_d,
            display=fmt_pct(gap_d),
            label=_LABELS[status],
            threshold=f"이평선 아래 신호 · {cfg['strong_gap_at_or_below'] * 100:.0f}% 이상 이탈 강한 신호",
            as_of=as_of(s),
            details=details,
            history=to_points(s),
            overlays=overlays,
        )

from __future__ import annotations

from typing import Optional

import pandas as pd

from app.indicators.base import (
    NEUTRAL, SIGNAL, STRONG, EvalContext, Indicator, IndicatorResult, as_of, register, to_points,
)
from app.indicators.moving_average import to_weekly

_LABELS = {STRONG: "일봉·주봉 모두 과매도", SIGNAL: "일봉·주봉 중 하나 과매도", NEUTRAL: "과매도 아님"}


def wilder_rsi(s: pd.Series, period: int) -> pd.Series:
    """Wilder 평활 RSI (TradingView ta.rsi와 같은 방식)."""
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    out = 100 - 100 / (1 + rs)
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    return out.where(avg_gain.notna())


def grade(daily: float, weekly: Optional[float], cfg: dict) -> str:
    hits = int(daily <= cfg["daily_at_or_below"])
    if weekly is not None:
        hits += int(weekly <= cfg["weekly_at_or_below"])
    if hits == 2:
        return STRONG
    if hits == 1:
        return SIGNAL
    return NEUTRAL


def _mark(value: float, limit: float) -> str:
    return f"{value:.1f} ({'해당' if value <= limit else '미해당'})"


@register
class Rsi(Indicator):
    id = "rsi"
    name = "RSI (14, 일봉·주봉)"
    scope = "ticker"
    order = 40

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        period = int(cfg["period"])
        d_limit, w_limit = cfg["daily_at_or_below"], cfg["weekly_at_or_below"]
        s = ctx.get_daily(ctx.symbol).dropna()
        if len(s) <= period + 1:
            return self.insufficient(f"RSI 계산에 {period + 2}거래일 이상 필요합니다")

        daily = wilder_rsi(s, period).dropna()
        d = float(daily.iloc[-1])
        weekly = wilder_rsi(to_weekly(s), period).dropna()
        w = float(weekly.iloc[-1]) if not weekly.empty else None
        status = grade(d, w, cfg)

        details = {
            f"일봉 RSI({period})": _mark(d, d_limit),
            f"주봉 RSI({period})": _mark(w, w_limit) if w is not None else "데이터 부족",
        }
        overlays = {"주봉 RSI": to_points(weekly.reindex(daily.index, method="ffill"))} if w is not None else {}
        return self.make(
            status=status,
            value=d,
            display=f"일 {d:.1f} · 주 {w:.1f}" if w is not None else f"일 {d:.1f}",
            label=_LABELS[status],
            threshold=f"일봉 {d_limit} 이하 · 주봉 {w_limit} 이하 — 하나 해당 신호, 둘 다 해당 강한 신호",
            as_of=as_of(s),
            details=details,
            history=to_points(daily),
            overlays=overlays,
            thresholds=[d_limit, w_limit],
        )

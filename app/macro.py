"""거시 지표 탭: WTI, CPI(전년 대비), 실효 기준금리, 국채 2년·10년."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Dict, List, Optional

import pandas as pd

from app.indicators.base import to_points

YEARS = 20  # 차트에 보낼 기간

# (FRED 시리즈, 표시 이름, 단위, 변환)  — 변환: weekly = 주별 마지막 값, yoy = 전년 같은 달 대비 %
MACRO_SERIES = [
    ("DCOILWTICO", "WTI", "$", "weekly"),
    ("CPIAUCSL", "CPI (전년 대비)", "%", "yoy"),
    ("DFF", "기준금리(실효)", "%", "weekly"),
    ("DGS2", "국채 2년", "%", "weekly"),
    ("DGS10", "국채 10년", "%", "weekly"),
]


def yoy_percent(monthly_index: pd.Series) -> pd.Series:
    """월별 물가 지수 → 전년 같은 달 대비 상승률(%)."""
    s = monthly_index.dropna().sort_index()
    return ((s / s.shift(12) - 1) * 100).dropna()


def to_weekly_last(series: pd.Series) -> pd.Series:
    """일별 값 → 주(금요일 기준)별 마지막 값. 20년치를 차트에 가볍게 보내려는 것."""
    return series.dropna().resample("W-FRI").last().dropna()


def build_macro(fetch: Callable[[str, date], pd.Series], today: Optional[date] = None) -> dict:
    today = today or date.today()
    start = today - timedelta(days=365 * (YEARS + 2))   # CPI 전년 대비 계산용 1년 + 여유
    series: Dict[str, dict] = {}
    latest: Dict[str, dict] = {}
    failed: List[str] = []
    for sid, name, unit, transform in MACRO_SERIES:
        try:
            raw = fetch(sid, start)
        except Exception:
            raw = None
        if raw is None or len(raw.dropna()) == 0:
            failed.append(name)
            continue
        values = yoy_percent(raw) if transform == "yoy" else raw.dropna().sort_index()
        if values.empty:
            failed.append(name)
            continue
        chart = to_weekly_last(values) if transform == "weekly" else values
        series[sid] = {"name": name, "unit": unit, "points": to_points(chart, years=YEARS)}
        latest[sid] = {"value": round(float(values.iloc[-1]), 4), "date": values.index[-1].strftime("%Y-%m-%d")}
    if "DGS10" in latest and "DGS2" in latest:
        latest["SPREAD_10_2"] = {"value": round(latest["DGS10"]["value"] - latest["DGS2"]["value"], 4),
                                 "date": latest["DGS10"]["date"]}
    return {"series": series, "latest": latest, "failed": failed}

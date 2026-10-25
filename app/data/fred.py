"""미국 연준 FRED 시계열 (키 없이 CSV로 받기)."""
from __future__ import annotations

import io
from datetime import date

import httpx
import pandas as pd

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
TIMEOUT_SECONDS = 20


def parse_fred_csv(text: str) -> pd.Series:
    """FRED CSV(observation_date,<ID>)를 날짜 인덱스 Series로. 빈 값('.')은 뺀다."""
    df = pd.read_csv(io.StringIO(text))
    values = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    series = pd.Series(values.values, index=pd.to_datetime(df.iloc[:, 0]))
    return series.dropna().astype(float)


def fetch_fred(series_id: str, start: date) -> pd.Series:
    url = FRED_CSV.format(series_id=series_id, start=start.isoformat())
    try:
        resp = httpx.get(url, timeout=TIMEOUT_SECONDS, follow_redirects=True)
    except httpx.HTTPError:
        resp = httpx.get(url, timeout=TIMEOUT_SECONDS, follow_redirects=True)  # 1회 재시도
    resp.raise_for_status()
    return parse_fred_csv(resp.text)

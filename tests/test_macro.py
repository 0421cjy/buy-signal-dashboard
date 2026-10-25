from __future__ import annotations

from collections import Counter

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import DEFAULT_CONFIG
from app.data.fred import parse_fred_csv
from app.macro import MACRO_SERIES, build_macro, to_weekly_last, yoy_percent
from app.main import create_app


def monthly(values, start="2024-01-01"):
    return pd.Series([float(v) for v in values], index=pd.date_range(start, periods=len(values), freq="MS"))


def daily(values, start="2026-08-31"):
    return pd.Series([float(v) for v in values], index=pd.bdate_range(start, periods=len(values)))


def test_parse_fred_csv_drops_missing_values():
    s = parse_fred_csv("observation_date,DGS10\n2026-10-21,4.90\n2026-10-22,.\n2026-10-23,4.96\n")
    assert list(s.values) == [4.90, 4.96]
    assert s.index[-1] == pd.Timestamp("2026-10-23")


def test_yoy_percent_compares_same_month_last_year():
    s = yoy_percent(monthly([100] * 12 + [103, 104]))
    assert list(s.round(4).values) == [3.0, 4.0]
    assert s.index[0] == pd.Timestamp("2025-01-01")


def test_to_weekly_last_keeps_friday_close():
    s = to_weekly_last(daily([1, 2, 3, 4, 5, 6, 7]))   # 8/31(월)~9/8(화)
    assert list(s.values) == [5.0, 7.0]


def test_series_definitions():
    assert [sid for sid, *_ in MACRO_SERIES] == ["DCOILWTICO", "CPIAUCSL", "DFF", "DGS2", "DGS10"]


def fake_fetch(failing=()):
    data = {
        "DCOILWTICO": daily([70, 71, 72, 73, 74]),
        "CPIAUCSL": monthly([100] * 12 + [103]),
        "DFF": daily([3.88] * 5),
        "DGS2": daily([4.60, 4.61, 4.62, 4.63, 4.65]),
        "DGS10": daily([4.90, 4.91, 4.92, 4.94, 4.96]),
    }

    def fetch(series_id, start):
        if series_id in failing:
            raise ConnectionError("fred down")
        return data[series_id]

    return fetch


def test_build_macro_series_latest_and_spread():
    out = build_macro(fake_fetch())
    assert set(out["series"]) == {"DCOILWTICO", "CPIAUCSL", "DFF", "DGS2", "DGS10"}
    wti = out["series"]["DCOILWTICO"]
    assert wti["name"] == "WTI" and wti["unit"] == "$"
    assert out["series"]["CPIAUCSL"]["points"][-1]["value"] == pytest.approx(3.0)
    assert out["latest"]["DCOILWTICO"] == {"value": 74.0, "date": "2026-09-04"}
    assert out["latest"]["CPIAUCSL"]["value"] == pytest.approx(3.0)
    assert out["latest"]["SPREAD_10_2"]["value"] == pytest.approx(0.31)
    assert out["failed"] == []


def test_build_macro_partial_failure():
    out = build_macro(fake_fetch(failing=("DCOILWTICO", "DGS2")))
    assert "DCOILWTICO" not in out["series"] and "DGS2" not in out["series"]
    assert out["failed"] == ["WTI", "국채 2년"]
    assert "SPREAD_10_2" not in out["latest"]


def test_api_macro_shape_and_cache():
    calls = Counter()
    base = fake_fetch()

    def counting(series_id, start):
        calls[series_id] += 1
        return base(series_id, start)

    client = TestClient(create_app(config=DEFAULT_CONFIG, fetch_daily=lambda s: pd.Series(dtype=float),
                                   fetch_fear_greed=dict, fetch_name=str, fetch_fred=counting))
    body = client.get("/api/macro").json()
    assert set(body) == {"series", "latest", "failed", "fetched_at"}
    client.get("/api/macro")
    assert calls["DGS10"] == 1
    client.get("/api/macro?refresh=1")
    assert calls["DGS10"] == 2

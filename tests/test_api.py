from __future__ import annotations

from collections import Counter

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import DEFAULT_CONFIG
from app.main import create_app
from tests.helpers import series

FG = {"score": 15.0, "as_of": "2026-10-09", "history": []}
DATA = {
    "^VIX": series([20] * 50 + [31]),
    "^GSPC": series([100] * 50 + [85]),
    "AAPL": series([100] * 1100 + [90]),
    "123456.KQ": series([100] * 300 + [97]),
}


def make_client(daily=None, fg=None, calls=None):
    def fetch_daily(sym):
        if calls is not None:
            calls[sym] += 1
        if daily is not None:
            return daily(sym)
        return DATA.get(sym, pd.Series(dtype=float))

    app = create_app(
        config=DEFAULT_CONFIG,
        fetch_daily=fetch_daily,
        fetch_fear_greed=fg or (lambda: FG),
        fetch_name=lambda sym: f"Name of {sym}",
    )
    return TestClient(app)


def test_health():
    assert make_client().get("/api/health").json() == {"status": "ok"}


def test_market():
    body = make_client().get("/api/market").json()
    ids = [r["id"] for r in body["results"]]
    assert ids == ["fear_greed", "vix", "market_mdd"]
    assert body["score"] == {"met": 2, "strong": 2, "total": 2, "failed": 0}
    assert "fetched_at" in body


def test_market_partial_failure():
    def daily(sym):
        if sym == "^VIX":
            raise ConnectionError("yahoo down")
        return DATA[sym]

    body = make_client(daily=daily).get("/api/market").json()
    by_id = {r["id"]: r for r in body["results"]}
    assert by_id["vix"]["status"] == "error"
    assert by_id["fear_greed"]["status"] == "strong_signal"
    assert by_id["market_mdd"]["status"] == "signal"
    assert body["score"] == {"met": 1, "strong": 1, "total": 1, "failed": 1}


def test_ticker():
    body = make_client().get("/api/ticker/aapl").json()
    assert body["symbol"] == "AAPL"
    assert body["name"] == "Name of AAPL"
    assert [r["id"] for r in body["results"]] == ["rsi", "mdd", "moving_average"]


def test_ticker_korean_fallback():
    body = make_client().get("/api/ticker/123456").json()
    assert body["symbol"] == "123456.KQ"


def test_ticker_not_found():
    resp = make_client().get("/api/ticker/ZZZZ")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "종목을 찾을 수 없습니다: ZZZZ"


def test_ticker_network_failure_returns_502():
    def daily(sym):
        raise ConnectionError("offline")

    resp = make_client(daily=daily).get("/api/ticker/AAPL")
    assert resp.status_code == 502
    assert resp.json()["detail"].startswith("데이터 조회에 실패했습니다")


def test_cache_avoids_refetch():
    calls = Counter()
    client = make_client(calls=calls)
    client.get("/api/ticker/AAPL")
    client.get("/api/ticker/AAPL")
    assert calls["AAPL"] == 1


def test_refresh_refetches_each_symbol_once():
    calls = Counter()
    client = make_client(calls=calls)
    client.get("/api/ticker/AAPL")
    client.get("/api/ticker/AAPL?refresh=1")
    assert calls["AAPL"] == 2


def test_settings_exposes_auto_refresh_minutes():
    assert make_client().get("/api/settings").json() == {"auto_refresh_minutes": 10}


def test_settings_auto_refresh_can_be_disabled():
    import copy

    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["auto_refresh_minutes"] = 0
    client = TestClient(create_app(config=cfg, fetch_daily=lambda s: None, fetch_fear_greed=dict, fetch_name=str))
    assert client.get("/api/settings").json() == {"auto_refresh_minutes": 0}

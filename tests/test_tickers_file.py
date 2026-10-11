from __future__ import annotations

import json
from pathlib import Path

import pytest

TICKERS = Path(__file__).resolve().parent.parent / "static" / "tickers.json"
MARKETS = {"US", "ETF", "INDEX", "KOSPI", "KOSDAQ"}


def load():
    return json.loads(TICKERS.read_text(encoding="utf-8"))


def test_entries_have_required_fields():
    items = load()
    assert len(items) >= 100
    for item in items:
        assert set(item) <= {"symbol", "name", "ko", "market", "aliases"}, item
        assert item["symbol"] and item["name"] and item["market"] in MARKETS, item
        assert isinstance(item.get("aliases", []), list), item


def test_symbols_are_unique_and_normalized():
    symbols = [item["symbol"] for item in load()]
    assert len(symbols) == len(set(symbols))
    assert all(s == s.strip().upper() for s in symbols)


def test_korean_symbols_use_exchange_suffix():
    for item in load():
        if item["market"] == "KOSPI":
            assert item["symbol"].endswith(".KS"), item
        if item["market"] == "KOSDAQ":
            assert item["symbol"].endswith(".KQ"), item
        if item["market"] in ("KOSPI", "KOSDAQ"):
            assert item.get("ko"), item


@pytest.mark.live
def test_every_symbol_has_price_data():
    from app.data.prices import fetch_history

    missing = [item["symbol"] for item in load() if fetch_history(item["symbol"]).empty]
    assert missing == []

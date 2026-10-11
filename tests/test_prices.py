from __future__ import annotations

import pandas as pd
import pytest

from app.data.prices import TickerNotFound, candidate_symbols, clean_close, resolve_symbol
from tests.helpers import series


def test_candidate_symbols_normalizes():
    assert candidate_symbols(" aapl ") == ["AAPL"]
    assert candidate_symbols("brk-b") == ["BRK-B"]
    assert candidate_symbols("005930.ks") == ["005930.KS"]


def test_candidate_symbols_korean_code():
    assert candidate_symbols("005930") == ["005930.KS", "005930.KQ"]


def test_candidate_symbols_empty_raises():
    with pytest.raises(TickerNotFound):
        candidate_symbols("   ")


def test_clean_close_drops_nan_and_timezone():
    idx = pd.date_range("2026-01-05 09:30", periods=3, freq="D", tz="America/New_York")
    df = pd.DataFrame({"Close": [1.0, 2.0, float("nan")], "Open": [0, 0, 0]}, index=idx)
    s = clean_close(df)
    assert list(s.values) == [1.0, 2.0]
    assert s.index.tz is None
    assert s.index[0] == pd.Timestamp("2026-01-05")


def test_clean_close_empty():
    assert clean_close(None).empty
    assert clean_close(pd.DataFrame()).empty


def test_resolve_falls_back_to_kosdaq():
    data = {"035720.KS": pd.Series(dtype=float), "035720.KQ": series([1, 2])}
    assert resolve_symbol("035720", data.__getitem__) == "035720.KQ"


def test_resolve_not_found():
    with pytest.raises(TickerNotFound):
        resolve_symbol("ZZZZ", lambda sym: pd.Series(dtype=float))


def test_resolve_propagates_network_errors():
    def boom(sym):
        raise ConnectionError("offline")

    with pytest.raises(ConnectionError):
        resolve_symbol("AAPL", boom)

from __future__ import annotations

from typing import Callable, List, Optional

import pandas as pd

TIMEOUT_SECONDS = 10


class TickerNotFound(Exception):
    pass


def candidate_symbols(raw: str) -> List[str]:
    symbol = raw.strip().upper()
    if not symbol:
        raise TickerNotFound(raw)
    if len(symbol) == 6 and symbol.isdigit():
        return [f"{symbol}.KS", f"{symbol}.KQ"]
    return [symbol]


def clean_close(df: Optional[pd.DataFrame]) -> pd.Series:
    if df is None or df.empty or "Close" not in df.columns:
        return pd.Series(dtype=float)
    s = df["Close"].dropna().astype(float)
    index = pd.DatetimeIndex(s.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    s.index = index.normalize()
    return s[~s.index.duplicated(keep="last")]


def _with_retry(fn: Callable):
    try:
        return fn()
    except Exception:
        return fn()


def fetch_history(symbol: str) -> pd.Series:
    import yfinance as yf

    df = _with_retry(
        lambda: yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=False, timeout=TIMEOUT_SECONDS)
    )
    return clean_close(df)


def resolve_symbol(raw: str, get_daily: Callable[[str], pd.Series]) -> str:
    for candidate in candidate_symbols(raw):
        if not get_daily(candidate).empty:
            return candidate
    raise TickerNotFound(raw.strip())


def fetch_name(symbol: str) -> str:
    try:
        import yfinance as yf

        info = yf.Ticker(symbol).info or {}
        return info.get("shortName") or info.get("longName") or symbol
    except Exception:
        return symbol

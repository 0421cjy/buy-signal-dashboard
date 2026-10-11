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


def configure_yfinance() -> None:
    """yfinance는 기본적으로 네트워크 예외를 삼키고 빈 결과를 돌려준다.
    그러면 일시적 장애가 '종목 없음'으로 보이므로 예외가 올라오게 한다."""
    import yfinance as yf

    yf.config.debug.hide_exceptions = False


def _yf_download(symbol: str) -> pd.DataFrame:
    import yfinance as yf

    configure_yfinance()
    return yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=False, timeout=TIMEOUT_SECONDS)


def fetch_history(symbol: str, download: Callable[[str], pd.DataFrame] = _yf_download) -> pd.Series:
    """없는 종목이면 빈 Series, 네트워크 오류는 1회 재시도 후 예외를 그대로 올린다."""
    from yfinance.exceptions import YFTickerMissingError

    def attempt():
        try:
            return download(symbol)
        except YFTickerMissingError:
            return None
        except Exception as exc:
            # 없는 종목이면 Yahoo가 HTTP 404를 돌려준다
            if getattr(getattr(exc, "response", None), "status_code", None) == 404:
                return None
            raise

    return clean_close(_with_retry(attempt))


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

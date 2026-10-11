from __future__ import annotations

import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Set

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_config
from app.data import fear_greed, prices
from app.data.cache import TTLCache
from app.indicators.registry import evaluate_scope
from app.scoring import score

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(
    config: Optional[dict] = None,
    fetch_daily: Optional[Callable[[str], pd.Series]] = None,
    fetch_fear_greed: Optional[Callable[[], dict]] = None,
    fetch_name: Optional[Callable[[str], str]] = None,
) -> FastAPI:
    config = config or load_config()
    fetch_daily = fetch_daily or prices.fetch_history
    fetch_fear_greed = fetch_fear_greed or fear_greed.fetch_fear_greed
    fetch_name = fetch_name or prices.fetch_name
    cache = TTLCache(config["cache_ttl_seconds"])
    indicators_cfg = config["indicators"]

    app = FastAPI(title="매수 기준 대시보드")

    def getters(refresh: bool):
        refreshed: Set[tuple] = set()  # 한 요청 안에서는 같은 키를 한 번만 새로 받는다

        def cached(key, factory):
            force = refresh and key not in refreshed
            refreshed.add(key)
            return cache.get_or_set(key, factory, refresh=force)

        def get_daily(symbol: str) -> pd.Series:
            return cached(("daily", symbol), lambda: fetch_daily(symbol))

        def get_fear_greed() -> dict:
            return cached(("fear_greed",), fetch_fear_greed)

        def get_name(symbol: str) -> str:
            return cached(("name", symbol), lambda: fetch_name(symbol))

        return get_daily, get_fear_greed, get_name

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/market")
    def market(refresh: int = 0):
        get_daily, get_fg, _ = getters(bool(refresh))
        results = evaluate_scope("market", indicators_cfg, get_daily, get_fg)
        return {"results": results, "score": score(results), "fetched_at": datetime.now().isoformat(timespec="seconds")}

    @app.get("/api/ticker/{symbol}")
    def ticker(symbol: str, refresh: int = 0):
        get_daily, get_fg, get_name = getters(bool(refresh))
        try:
            resolved = prices.resolve_symbol(symbol, get_daily)
        except prices.TickerNotFound:
            raise HTTPException(status_code=404, detail=f"종목을 찾을 수 없습니다: {symbol.strip()}")
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"데이터 조회에 실패했습니다: {exc}")
        results = evaluate_scope("ticker", indicators_cfg, get_daily, get_fg, symbol=resolved)
        return {
            "symbol": resolved,
            "name": get_name(resolved),
            "results": results,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")
    return app


def run() -> None:
    import uvicorn

    config = load_config()
    host, port = config["server"]["host"], int(config["server"]["port"])
    if config["server"].get("open_browser", True):
        threading.Timer(1.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(create_app(config), host=host, port=port)

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx

URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/{start}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://edition.cnn.com/",
}
TIMEOUT_SECONDS = 10
HISTORY_YEARS = 5


def parse(payload: dict) -> dict:
    current = payload["fear_and_greed"]
    points = payload.get("fear_and_greed_historical", {}).get("data", [])
    history = [
        {
            "date": datetime.fromtimestamp(p["x"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
            "value": round(float(p["y"]), 1),
        }
        for p in points
    ]
    return {"score": float(current["score"]), "as_of": str(current["timestamp"])[:10], "history": history}


def fetch_fear_greed() -> dict:
    start = (date.today() - timedelta(days=365 * HISTORY_YEARS)).isoformat()
    url = URL.format(start=start)

    def get():
        resp = httpx.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()

    try:
        payload = get()
    except Exception:
        payload = get()
    return parse(payload)

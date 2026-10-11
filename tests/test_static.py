from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import DEFAULT_CONFIG
from app.main import create_app


def client():
    return TestClient(create_app(config=DEFAULT_CONFIG, fetch_daily=lambda s: None, fetch_fear_greed=dict, fetch_name=str))


def test_index_served():
    resp = client().get("/")
    assert resp.status_code == 200
    assert "매수 기준 체크" in resp.text
    assert "chart.umd.min.js" in resp.text


def test_assets_served():
    c = client()
    assert c.get("/static/app.js").status_code == 200
    assert c.get("/static/style.css").status_code == 200


def test_page_and_assets_revalidate_after_updates():
    c = client()
    for path in ("/", "/static/app.js", "/static/style.css"):
        assert c.get(path).headers.get("cache-control") == "no-cache", path

from __future__ import annotations

from app.data.fear_greed import parse


def test_parse_cnn_payload():
    payload = {
        "fear_and_greed": {"score": 17.4286, "rating": "extreme fear", "timestamp": "2026-10-09T23:59:57+00:00"},
        "fear_and_greed_historical": {
            "data": [
                {"x": 1760054400000.0, "y": 30.0, "rating": "fear"},
                {"x": 1760140800000.0, "y": 17.4286, "rating": "extreme fear"},
            ]
        },
    }
    out = parse(payload)
    assert out["score"] == 17.4286
    assert out["as_of"] == "2026-10-09"
    assert out["history"] == [{"date": "2025-10-10", "value": 30.0}, {"date": "2025-10-11", "value": 17.4}]


def test_parse_without_history():
    out = parse({"fear_and_greed": {"score": 50, "timestamp": "2026-10-09T00:00:00+00:00"}})
    assert out["history"] == []

from __future__ import annotations

from app.scoring import score


def r(status, scored=True):
    return {"status": status, "scored": scored}


def test_counts_only_scored_and_evaluated():
    results = [
        r("strong_signal"),
        r("signal"),
        r("neutral"),
        r("error"),
        r("insufficient_data"),
        r("strong_signal", scored=False),
    ]
    assert score(results) == {"met": 2, "strong": 1, "total": 3, "failed": 2}


def test_empty():
    assert score([]) == {"met": 0, "strong": 0, "total": 0, "failed": 0}

from __future__ import annotations

from typing import List

from app.indicators.base import NEUTRAL, SIGNAL, STRONG

_EVALUATED = (STRONG, SIGNAL, NEUTRAL)


def score(results: List[dict]) -> dict:
    scored = [r for r in results if r["scored"]]
    evaluated = [r for r in scored if r["status"] in _EVALUATED]
    return {
        "met": sum(r["status"] in (STRONG, SIGNAL) for r in evaluated),
        "strong": sum(r["status"] == STRONG for r in evaluated),
        "total": len(evaluated),
        "failed": len(scored) - len(evaluated),
    }

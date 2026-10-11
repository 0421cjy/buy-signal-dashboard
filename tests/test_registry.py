from __future__ import annotations

import pandas as pd

from app.indicators.base import (
    NEUTRAL, SIGNAL, STRONG, ERROR, Indicator, fmt_pct, register, strongest, to_points,
)
from app.indicators.registry import evaluate_scope, indicators_for
from tests.helpers import series


@register
class _OkIndicator(Indicator):
    id = "_ok"
    name = "OK"
    scope = "_test"
    order = 2

    def evaluate(self, ctx):
        return self.make(status=NEUTRAL, value=float(ctx.config.get("x", 1)))


@register
class _BoomIndicator(Indicator):
    id = "_boom"
    name = "Boom"
    scope = "_test"
    order = 1

    def evaluate(self, ctx):
        ctx.get_daily("X")
        raise AssertionError("unreachable")


def _raise(_sym):
    raise RuntimeError("network down")


def test_indicators_for_filters_scope_order_and_enabled():
    ids = [i.id for i in indicators_for("_test", {})]
    assert ids == ["_boom", "_ok"]
    ids = [i.id for i in indicators_for("_test", {"_boom": {"enabled": False}})]
    assert ids == ["_ok"]


def test_evaluate_scope_isolates_failures_and_passes_config():
    results = evaluate_scope("_test", {"_ok": {"x": 7}}, get_daily=_raise, get_fear_greed=dict)
    by_id = {r["id"]: r for r in results}
    assert by_id["_boom"]["status"] == ERROR
    assert "network down" in by_id["_boom"]["error"]
    assert by_id["_ok"]["status"] == NEUTRAL
    assert by_id["_ok"]["value"] == 7.0
    assert by_id["_ok"]["scope"] == "_test"
    assert by_id["_ok"]["scored"] is True


def test_strongest():
    assert strongest(NEUTRAL, SIGNAL) == SIGNAL
    assert strongest(SIGNAL, STRONG, NEUTRAL) == STRONG
    assert strongest(NEUTRAL) == NEUTRAL


def test_to_points_trims_years_drops_nan_and_scales():
    s = series([1.0] * 1500)
    s.iloc[-2] = float("nan")
    points = to_points(s, years=1, scale=100)
    assert points[-1]["value"] == 100.0
    assert all(p["value"] == 100.0 for p in points)
    assert 250 <= len(points) <= 262
    assert points[0]["date"] >= (s.index[-1] - pd.DateOffset(years=1)).strftime("%Y-%m-%d")


def test_fmt_pct():
    assert fmt_pct(-0.162) == "-16.2%"
    assert fmt_pct(0.12) == "+12.0%"

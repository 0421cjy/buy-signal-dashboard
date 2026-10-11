from __future__ import annotations

import pytest

from app.data.cache import TTLCache


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_caches_within_ttl_and_expires_after():
    clock = FakeClock()
    cache = TTLCache(10, clock=clock)
    calls = []

    def factory():
        calls.append(1)
        return len(calls)

    assert cache.get_or_set("k", factory) == 1
    clock.now = 9.9
    assert cache.get_or_set("k", factory) == 1
    clock.now = 10.0
    assert cache.get_or_set("k", factory) == 2


def test_refresh_bypasses_and_updates_cache():
    cache = TTLCache(100, clock=FakeClock())
    values = iter([1, 2])
    assert cache.get_or_set("k", lambda: next(values)) == 1
    assert cache.get_or_set("k", lambda: next(values), refresh=True) == 2
    assert cache.get_or_set("k", lambda: 99) == 2


def test_exceptions_are_not_cached():
    cache = TTLCache(100, clock=FakeClock())

    def boom():
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        cache.get_or_set("k", boom)
    assert cache.get_or_set("k", lambda: "ok") == "ok"

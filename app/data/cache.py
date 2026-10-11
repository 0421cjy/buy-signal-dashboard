from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Hashable, Tuple


class TTLCache:
    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.ttl = ttl_seconds
        self._clock = clock
        self._store: Dict[Hashable, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: Hashable, factory: Callable[[], Any], refresh: bool = False) -> Any:
        now = self._clock()
        if not refresh:
            with self._lock:
                hit = self._store.get(key)
            if hit is not None and now - hit[0] < self.ttl:
                return hit[1]
        value = factory()
        with self._lock:
            self._store[key] = (self._clock(), value)
        return value

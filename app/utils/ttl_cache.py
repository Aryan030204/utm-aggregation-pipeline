from __future__ import annotations

import threading
import time
from typing import Any, Callable, Hashable


class TTLCache:
    """Minimal thread-safe in-process TTL cache. A ttl_seconds <= 0 disables caching."""

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._items: dict[Hashable, tuple[float, Any]] = {}

    def get(self, key: Hashable, default: Any = None) -> Any:
        if self._ttl <= 0:
            return default
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return default
            stored_at, value = entry
            if self._clock() - stored_at >= self._ttl:
                del self._items[key]
                return default
            return value

    def set(self, key: Hashable, value: Any) -> None:
        if self._ttl <= 0:
            return
        with self._lock:
            now = self._clock()
            # Evict expired entries so date-keyed entries can't pile up in a long-lived process.
            for stale_key in [k for k, (stored_at, _) in self._items.items() if now - stored_at >= self._ttl]:
                del self._items[stale_key]
            self._items[key] = (now, value)

    def invalidate(self, key: Hashable | None = None) -> None:
        with self._lock:
            if key is None:
                self._items.clear()
            else:
                self._items.pop(key, None)

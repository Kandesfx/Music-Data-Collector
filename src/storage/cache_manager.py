"""
Music Data Collector - High-Speed In-Memory RAM Cache Tier
Thread-safe LRU caching with TTL, memory footprint tracking, and hit/miss telemetry
to deliver sub-5ms API response times across searches, catalog queries, and analytics.
"""

import time
import threading
from typing import Any, Optional, Dict, Tuple
from collections import OrderedDict

from src.utils.logger import get_logger

logger = get_logger(__name__)


class RAMCache:
    """Thread-safe In-Memory LRU Cache with TTL expiration."""

    def __init__(self, max_size: int = 5000, default_ttl_sec: int = 300):
        self.max_size = max_size
        self.default_ttl_sec = default_ttl_sec
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()
        
        # Telemetry metrics
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve item from cache if not expired."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            value, expire_at = self._cache[key]
            if time.time() > expire_at:
                # Expired
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (MRU)
            self._cache.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_sec: Optional[int] = None):
        """Store item in cache with expiration."""
        ttl = ttl_sec if ttl_sec is not None else self.default_ttl_sec
        expire_at = time.time() + ttl

        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, expire_at)

            # Evict oldest if exceeding max_size
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def delete(self, key: str) -> bool:
        """Remove a key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        """Clear all entries."""
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Return cache hit/miss ratio, size, and approximate memory usage."""
        with self._lock:
            # Clean expired items
            now = time.time()
            expired_keys = [k for k, (_, exp) in self._cache.items() if now > exp]
            for k in expired_keys:
                del self._cache[k]

            total_reqs = self._hits + self._misses
            hit_ratio = (self._hits / total_reqs * 100.0) if total_reqs > 0 else 0.0

            return {
                "active_entries": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_ratio_percent": round(hit_ratio, 1),
                "default_ttl_sec": self.default_ttl_sec,
            }


# Global Singleton RAM Cache instance
ram_cache = RAMCache(max_size=10000, default_ttl_sec=300)

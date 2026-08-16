"""
Music Data Collector - Rate Limiter
Ensures API requests stay within rate limits to avoid being blocked.
"""

import time
import threading
from collections import deque
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Thread-safe rate limiter using a sliding window approach.
    
    Usage:
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        limiter.wait()  # blocks until a request slot is available
        # ... make API request ...
    """

    def __init__(self, max_requests: int, window_seconds: float, name: str = "default"):
        """
        Args:
            max_requests: Maximum number of requests allowed in the window.
            window_seconds: Time window in seconds.
            name: Identifier for logging purposes.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self._timestamps = deque()
        self._lock = threading.Lock()
        self._total_waits = 0
        self._total_requests = 0

    def wait(self):
        """
        Block until a request slot is available within the rate limit window.
        Call this before every API request.
        """
        with self._lock:
            now = time.time()

            # Remove timestamps outside the current window
            while self._timestamps and self._timestamps[0] <= now - self.window_seconds:
                self._timestamps.popleft()

            # If at limit, wait until the oldest request expires
            if len(self._timestamps) >= self.max_requests:
                wait_time = self._timestamps[0] + self.window_seconds - now
                if wait_time > 0:
                    self._total_waits += 1
                    logger.debug(
                        f"[RateLimiter:{self.name}] Rate limit reached, "
                        f"waiting {wait_time:.2f}s..."
                    )
                    time.sleep(wait_time)

            # Record this request
            self._timestamps.append(time.time())
            self._total_requests += 1

    def get_stats(self) -> dict:
        """Return rate limiter statistics."""
        return {
            "name": self.name,
            "total_requests": self._total_requests,
            "total_waits": self._total_waits,
            "current_window_usage": len(self._timestamps),
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
        }


class SimpleDelay:
    """
    Simple fixed-delay rate limiter. Adds a constant delay between requests.
    Simpler alternative to sliding-window for sequential access patterns.
    """

    def __init__(self, delay_seconds: float = 0.5):
        """
        Args:
            delay_seconds: Minimum time between requests.
        """
        self.delay_seconds = delay_seconds
        self._last_request_time = 0.0
        self._lock = threading.Lock()

    def wait(self):
        """Wait until enough time has passed since the last request."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.delay_seconds:
                sleep_time = self.delay_seconds - elapsed
                time.sleep(sleep_time)
            self._last_request_time = time.time()

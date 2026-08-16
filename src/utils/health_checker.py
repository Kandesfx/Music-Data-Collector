"""
Music Data Collector - Health Checker Module
Monitors pipeline download success/failure rates and triggers intelligent pauses or halts.
"""

from typing import Dict, Any, List
from collections import deque

from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class HealthChecker:
    """
    Tracks recent download outcomes to detect severe bot-detection or network throttling.
    Triggers auto-pause if failure rates exceed safe thresholds.
    """

    def __init__(
        self,
        fail_threshold: int = settings.HEALTH_FAIL_THRESHOLD,
        window_size: int = settings.HEALTH_WINDOW_SIZE,
        max_pauses: int = settings.HEALTH_MAX_PAUSES,
        pause_seconds: int = settings.HEALTH_PAUSE_SECONDS,
    ):
        self.fail_threshold = fail_threshold
        self.window_size = window_size
        self.max_pauses = max_pauses
        self.pause_seconds = pause_seconds
        self.recent_results: deque = deque(maxlen=window_size)
        self.pause_count: int = 0
        self.total_recorded: int = 0
        self.total_fails: int = 0

    def record(self, success: bool):
        """Record the outcome (True for success, False for fail) of a download attempt."""
        self.recent_results.append(success)
        self.total_recorded += 1
        if not success:
            self.total_fails += 1

    def should_pause(self) -> bool:
        """
        Check if the failure rate in the current window exceeds threshold.
        """
        if len(self.recent_results) < min(self.window_size, self.fail_threshold):
            return False

        fails_in_window = sum(1 for res in self.recent_results if not res)
        return fails_in_window >= self.fail_threshold

    def should_stop(self) -> bool:
        """
        Returns True if maximum allowed pauses have been exceeded without recovery.
        """
        return self.pause_count >= self.max_pauses

    def trigger_pause(self) -> int:
        """Increment pause counter, reset window, and return pause duration in seconds."""
        self.pause_count += 1
        self.recent_results.clear()
        logger.warning(
            f"HealthChecker: Triggered pause #{self.pause_count}/{self.max_pauses} "
            f"for {self.pause_seconds} seconds due to high failure rate."
        )
        return self.pause_seconds

    def reset_pauses(self):
        """Reset pause counter upon sustained recovery."""
        if self.pause_count > 0:
            logger.info("HealthChecker: Recovery detected. Resetting pause counter.")
            self.pause_count = 0

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic metrics for dashboard or logs."""
        window_count = len(self.recent_results)
        window_fails = sum(1 for res in self.recent_results if not res)
        fail_rate = (window_fails / window_count * 100) if window_count > 0 else 0.0

        if self.should_stop():
            health_label = "CRITICAL"
        elif self.should_pause():
            health_label = "UNHEALTHY"
        elif window_fails > 0:
            health_label = "DEGRADED"
        else:
            health_label = "HEALTHY"

        return {
            "health": health_label,
            "recent_window_size": window_count,
            "recent_fails": window_fails,
            "recent_fail_rate_pct": round(fail_rate, 1),
            "pause_count": self.pause_count,
            "max_pauses": self.max_pauses,
            "total_recorded": self.total_recorded,
            "total_fails": self.total_fails,
        }

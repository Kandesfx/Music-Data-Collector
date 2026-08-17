"""
Music Data Collector - Proxy Manager Module
Manages a pool of HTTP/SOCKS4/SOCKS5 proxies with live speed measurement,
failure detection, rotation strategies, and direct MongoDB synchronization.
"""

import time
import random
from itertools import cycle
from typing import List, Optional, Dict, Any

import requests
from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProxyManager:
    """Provides proxy rotation, live latency speed tests, and fault-tolerant tracking."""

    def __init__(
        self,
        proxy_list: Optional[List[str]] = None,
        enabled: Optional[bool] = None,
        strategy: Optional[str] = None,
        db_manager: Optional[Any] = None,
    ):
        self.enabled = enabled if enabled is not None else settings.PROXY_ENABLED
        self.strategy = (strategy or settings.PROXY_ROTATION).lower()
        self.db_manager = db_manager
        self.proxies: List[str] = []

        if db_manager and hasattr(db_manager, "get_active_proxies"):
            db_proxies = db_manager.get_active_proxies()
            if db_proxies:
                self.proxies = db_proxies

        if not self.proxies:
            self.proxies = list(proxy_list if proxy_list is not None else settings.PROXY_LIST)

        self._pool = cycle(self.proxies) if self.proxies else None
        self._fail_counts: Dict[str, int] = {p: 0 for p in self.proxies}

        if self.enabled and self.proxies:
            logger.info(f"ProxyManager enabled with {len(self.proxies)} proxies (strategy: {self.strategy}).")
        elif self.enabled and not self.proxies:
            logger.warning("ProxyManager is enabled but no proxies were provided in configuration.")

    def sync_from_db(self):
        """Refresh the in-memory rotation pool directly from MongoDB."""
        if self.db_manager and hasattr(self.db_manager, "get_active_proxies"):
            active = self.db_manager.get_active_proxies()
            self.proxies = active
            self._pool = cycle(self.proxies) if self.proxies else None
            logger.info(f"🔄 Synced {len(self.proxies)} active proxies from MongoDB pool.")

    def get_proxy(self) -> Optional[str]:
        """
        Get the next active proxy according to the configured rotation strategy.
        Strategies:
        - 'round_robin': Sequential rotation through active pool
        - 'lowest_latency': Selects the proxy with fastest ping time
        - 'random': Selects a random active proxy
        - 'failover_only': Uses first proxy (e.g. Cloudflare WARP), only fails over on errors
        """
        if not self.enabled or not self.proxies:
            return None

        if self.strategy == "random":
            return random.choice(self.proxies)

        elif self.strategy == "lowest_latency":
            # If db_manager has proxy docs with latency info, pick lowest latency
            if self.db_manager and hasattr(self.db_manager, "get_all_proxies"):
                try:
                    all_p = self.db_manager.get_all_proxies()
                    active_p = [p for p in all_p if p.get("is_active") and p.get("status") == "alive"]
                    if active_p:
                        sorted_p = sorted(active_p, key=lambda x: x.get("latency_ms", 9999))
                        return sorted_p[0].get("url")
                except Exception:
                    pass
            return self.proxies[0]

        elif self.strategy == "failover_only":
            # Always return primary unless failed
            return self.proxies[0]

        else:  # round_robin (default)
            if not self._pool:
                self._pool = cycle(self.proxies)
            return next(self._pool)

    def report_failure(self, proxy: str):
        """Record a connection failure on a proxy; remove/quarantine if failure threshold is reached."""
        if not proxy or proxy not in self.proxies:
            return

        self._fail_counts[proxy] = self._fail_counts.get(proxy, 0) + 1
        fails = self._fail_counts[proxy]
        logger.warning(f"Proxy failure reported for '{proxy}' ({fails}/3 failures).")

        if fails >= 3:
            logger.error(f"Quarantining dead proxy from rotation: '{proxy}'")
            if proxy in self.proxies:
                self.proxies.remove(proxy)
                self._pool = cycle(self.proxies) if self.proxies else None
            # Update status in db if available
            if self.db_manager and hasattr(self.db_manager, "update_proxy_status"):
                try:
                    all_p = self.db_manager.get_all_proxies()
                    for p in all_p:
                        if p.get("url") == proxy:
                            self.db_manager.update_proxy_status(p["id"], status="dead", latency_ms=0, error="Quarantined after 3 consecutive failures")
                            break
                except Exception:
                    pass

    def report_success(self, proxy: str):
        """Reset consecutive failure counter on successful request."""
        if proxy in self._fail_counts:
            self._fail_counts[proxy] = 0

    def toggle(self, enable: bool):
        """Enable or disable proxy usage at runtime."""
        self.enabled = enable
        logger.info(f"ProxyManager status updated: enabled={self.enabled}")

    def set_strategy(self, strategy: str):
        """Set proxy rotation strategy."""
        valid_strategies = ["round_robin", "lowest_latency", "random", "failover_only"]
        clean_strat = strategy.lower().strip()
        if clean_strat in valid_strategies:
            self.strategy = clean_strat
            logger.info(f"Proxy rotation strategy set to: '{self.strategy}'")

    def add_proxy(self, proxy_url: str):
        """Add a new proxy to the active pool."""
        clean_url = proxy_url.strip()
        if clean_url and clean_url not in self.proxies:
            self.proxies.append(clean_url)
            self._fail_counts[clean_url] = 0
            self._pool = cycle(self.proxies)
            logger.info(f"Added new proxy: '{clean_url}' (Total active: {len(self.proxies)})")

    @staticmethod
    def inspect_proxy_egress(proxy_url: Optional[str] = None, timeout: int = 6) -> Dict[str, Any]:
        """
        Inspect the public IP address, ISP, and Country visible to outside servers.
        If proxy_url is None, inspects direct host connection.
        """
        proxies = None
        if proxy_url and proxy_url.strip():
            proxies = {"http": proxy_url.strip(), "https": proxy_url.strip()}

        start_t = time.perf_counter()
        try:
            r = requests.get(
                "https://ipinfo.io/json",
                proxies=proxies,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DATN-Shield/2026"}
            )
            latency = int((time.perf_counter() - start_t) * 1000)
            if r.status_code == 200:
                data = r.json()
                return {
                    "success": True,
                    "ip": data.get("ip", "Unknown"),
                    "isp": data.get("org", "Unknown ISP"),
                    "city": data.get("city", "Unknown City"),
                    "country": data.get("country", "Unknown Country"),
                    "latency_ms": max(1, latency),
                    "is_datacenter": any(kw in data.get("org", "").lower() for kw in ["oracle", "amazon", "google", "digitalocean", "microsoft", "ovh", "hetzner"]),
                }
        except Exception as e:
            return {
                "success": False,
                "ip": "Failed to connect",
                "isp": "N/A",
                "city": "N/A",
                "country": "N/A",
                "latency_ms": 0,
                "error": str(e),
            }

        return {
            "success": False,
            "ip": "Unknown",
            "isp": "N/A",
            "city": "N/A",
            "country": "N/A",
            "latency_ms": 0,
            "error": "No response received",
        }

    @staticmethod
    def test_proxy_connection(proxy_url: str, timeout: int = 5) -> Dict[str, Any]:
        """
        Test proxy connectivity and measure response latency (ping ms).
        Supports HTTP, HTTPS, SOCKS4, and SOCKS5 proxies.
        """
        proxy_url = proxy_url.strip()
        if not proxy_url:
            return {"status": "dead", "latency_ms": 0, "error": "URL proxy trống"}

        proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }

        test_urls = [
            "https://httpbin.org/ip",
            "https://www.google.com",
            "https://api.spotify.com",
        ]

        start_time = time.perf_counter()
        last_error = None

        for target in test_urls:
            try:
                resp = requests.get(
                    target,
                    proxies=proxies,
                    timeout=timeout,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DATN/2026"},
                )
                latency = int((time.perf_counter() - start_time) * 1000)
                if resp.status_code in (200, 204, 301, 302, 401, 403):
                    ip = ""
                    try:
                        ip = resp.json().get("origin", "")
                    except Exception:
                        pass
                    return {
                        "status": "alive",
                        "latency_ms": max(1, latency),
                        "status_code": resp.status_code,
                        "ip": ip,
                        "error": None,
                    }
            except Exception as ex:
                last_error = str(ex)

        latency = int((time.perf_counter() - start_time) * 1000)
        return {
            "status": "dead",
            "latency_ms": latency,
            "error": last_error or "Timeout hoặc kết nối thất bại",
        }

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic proxy information for dashboard."""
        return {
            "enabled": self.enabled,
            "strategy": self.strategy,
            "total_proxies": len(self.proxies),
            "proxies": self.proxies,
        }


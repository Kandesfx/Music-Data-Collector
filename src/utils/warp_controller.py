"""
Music Data Collector - Cloudflare WARP Controller Module
Manages the local Cloudflare WARP daemon (warp-cli) in SOCKS5 proxy mode (port 40000)
to mask the Oracle Cloud Datacenter IP with Cloudflare Anycast residential/consumer IP.
"""

import subprocess
import shutil
import time
import requests
from typing import Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WarpController:
    """Controls Cloudflare WARP client CLI and inspects egress connectivity."""

    DEFAULT_PORT = 40000
    DEFAULT_PROXY_URL = f"socks5://127.0.0.1:{DEFAULT_PORT}"

    @classmethod
    def is_installed(cls) -> bool:
        """Check if warp-cli is installed on the host system."""
        return shutil.which("warp-cli") is not None

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """
        Get current WARP client status and proxy port information.
        """
        if not cls.is_installed():
            return {
                "installed": False,
                "status": "NOT_INSTALLED",
                "is_connected": False,
                "proxy_port": cls.DEFAULT_PORT,
                "proxy_url": cls.DEFAULT_PROXY_URL,
                "message": "Cloudflare WARP (warp-cli) chưa được cài đặt trên máy chủ.",
            }

        try:
            res = subprocess.run(["warp-cli", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            output = (res.stdout + res.stderr).strip()
            is_connected = "Connected" in output or "Status update: Connected" in output
            
            # Check mode & settings
            mode_res = subprocess.run(["warp-cli", "mode"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            mode_str = (mode_res.stdout + mode_res.stderr).strip()

            return {
                "installed": True,
                "status": "CONNECTED" if is_connected else "DISCONNECTED",
                "is_connected": is_connected,
                "proxy_port": cls.DEFAULT_PORT,
                "proxy_url": cls.DEFAULT_PROXY_URL,
                "mode": mode_str,
                "raw_status": output,
                "message": "Cloudflare WARP đang hoạt động (SOCKS5 Gateway sẵn sàng)" if is_connected else "Cloudflare WARP đang ở trạng thái ngắt kết nối.",
            }
        except Exception as e:
            return {
                "installed": True,
                "status": "ERROR",
                "is_connected": False,
                "proxy_port": cls.DEFAULT_PORT,
                "proxy_url": cls.DEFAULT_PROXY_URL,
                "message": f"Lỗi truy vấn trạng thái WARP: {e}",
            }

    @classmethod
    def connect(cls) -> bool:
        """Connect to Cloudflare WARP."""
        if not cls.is_installed():
            return False
        try:
            subprocess.run(["warp-cli", "connect"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            time.sleep(1)
            status = cls.get_status()
            logger.info(f"Cloudflare WARP connect result: {status['status']}")
            return status["is_connected"]
        except Exception as e:
            logger.error(f"Failed to connect Cloudflare WARP: {e}")
            return False

    @classmethod
    def disconnect(cls) -> bool:
        """Disconnect Cloudflare WARP."""
        if not cls.is_installed():
            return False
        try:
            subprocess.run(["warp-cli", "disconnect"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            time.sleep(1)
            status = cls.get_status()
            logger.info(f"Cloudflare WARP disconnect result: {status['status']}")
            return not status["is_connected"]
        except Exception as e:
            logger.error(f"Failed to disconnect Cloudflare WARP: {e}")
            return False

    @classmethod
    def test_egress_ip(cls) -> Dict[str, Any]:
        """
        Query public IP through WARP SOCKS5 proxy compared to direct connection.
        """
        result = {
            "direct_ip": "Unknown",
            "warp_ip": "Unknown",
            "warp_active": False,
            "latency_ms": 0,
            "isp": "Unknown",
            "country": "Unknown",
        }

        # 1. Check Direct IP
        try:
            r = requests.get("https://api.ipify.org?format=json", timeout=4)
            if r.status_code == 200:
                result["direct_ip"] = r.json().get("ip", "Unknown")
        except Exception:
            pass

        # 2. Check WARP SOCKS5 Egress IP
        start_t = time.perf_counter()
        try:
            proxies = {
                "http": cls.DEFAULT_PROXY_URL,
                "https": cls.DEFAULT_PROXY_URL,
            }
            r_warp = requests.get("https://ipinfo.io/json", proxies=proxies, timeout=6)
            if r_warp.status_code == 200:
                data = r_warp.json()
                result["warp_ip"] = data.get("ip", "Unknown")
                result["isp"] = data.get("org", "Cloudflare, Inc.")
                result["country"] = data.get("country", "SG")
                result["warp_active"] = (result["warp_ip"] != result["direct_ip"])
                result["latency_ms"] = int((time.perf_counter() - start_t) * 1000)
        except Exception as ex:
            result["error"] = str(ex)

        return result

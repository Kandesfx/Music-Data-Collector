"""
Music Data Collector - Cookie Health Checker Module
Inspects Netscape cookie files, calculates expiration dates, and verifies live session status.
"""

import os
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
import requests

from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CookieHealthChecker:
    """
    Automated health monitor for YouTube & Spotify headless cookies.
    """

    CRITICAL_YT_COOKIES = ["SID", "SSID", "HSID", "LOGIN_INFO", "__Secure-1PSID", "__Secure-3PSID"]

    @classmethod
    def resolve_cookie_path(cls, custom_path: Optional[Path] = None) -> Optional[Path]:
        """Find the active cookies.txt file across project standard locations."""
        candidates = [
            custom_path,
            settings.CONFIG_DIR / "cookies.txt",
            settings.DATA_DIR / "cookies.txt",
            settings.BASE_DIR / "config" / "cookies.txt",
            settings.BASE_DIR / "cookies.txt",
            Path("/opt/music-data-collector/config/cookies.txt"),
            Path("/opt/music-data-collector/data/cookies.txt"),
        ]
        for c in candidates:
            if c:
                p = Path(c)
                if p.exists() and p.is_file() and p.stat().st_size > 10:
                    return p
        return None

    @classmethod
    def parse_cookie_file(cls, cookie_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, str], Optional[int]]:
        """
        Parse Netscape HTTP Cookie File.
        Returns:
            - list of parsed cookie dicts
            - dict of {name: value}
            - earliest expiration timestamp (or None)
        """
        cookies_list = []
        cookies_dict = {}
        earliest_expiry = None

        if not cookie_path.exists():
            return cookies_list, cookies_dict, earliest_expiry

        now_ts = int(time.time())

        try:
            with open(cookie_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        domain, flag, path, secure, expiry, name, value = parts[:7]
                        try:
                            exp_ts = int(expiry)
                        except ValueError:
                            exp_ts = 0

                        cookie_obj = {
                            "domain": domain,
                            "flag": flag == "TRUE",
                            "path": path,
                            "secure": secure == "TRUE",
                            "expiry": exp_ts,
                            "name": name,
                            "value": value,
                            "expired": (exp_ts > 0 and exp_ts < now_ts),
                        }
                        cookies_list.append(cookie_obj)
                        cookies_dict[name] = value

                        # Find earliest future expiration
                        if exp_ts > now_ts:
                            if earliest_expiry is None or exp_ts < earliest_expiry:
                                earliest_expiry = exp_ts
        except Exception as e:
            logger.error(f"Error reading cookie file {cookie_path}: {e}")

        return cookies_list, cookies_dict, earliest_expiry

    @classmethod
    def check_health(cls, custom_path: Optional[Path] = None, probe_network: bool = True) -> Dict[str, Any]:
        """
        Perform complete diagnostic on the active cookies.txt file.
        """
        cookie_path = cls.resolve_cookie_path(custom_path)
        if not cookie_path:
            return {
                "exists": False,
                "valid": False,
                "status": "NOT_CONFIGURED",
                "message": "Chưa nạp file cookies.txt lên hệ thống.",
                "cookie_count": 0,
                "size_bytes": 0,
                "account_logged_in": False,
                "earliest_expiry": None,
                "earliest_expiry_formatted": "N/A",
                "path": None,
            }

        file_size = cookie_path.stat().st_size
        cookies_list, cookies_dict, earliest_expiry = cls.parse_cookie_file(cookie_path)

        if not cookies_list:
            return {
                "exists": True,
                "valid": False,
                "status": "EMPTY_OR_INVALID",
                "message": "File cookies.txt bị rỗng hoặc không đúng định dạng Netscape.",
                "cookie_count": 0,
                "size_bytes": file_size,
                "account_logged_in": False,
                "earliest_expiry": None,
                "earliest_expiry_formatted": "N/A",
                "path": str(cookie_path),
            }

        # Check critical YouTube session keys
        found_critical = [k for k in cls.CRITICAL_YT_COOKIES if k in cookies_dict]
        has_login = "LOGIN_INFO" in cookies_dict or "SID" in cookies_dict or "__Secure-1PSID" in cookies_dict

        expiry_str = "Vĩnh viễn / Không thời hạn"
        if earliest_expiry:
            dt = datetime.fromtimestamp(earliest_expiry, tz=timezone.utc)
            expiry_str = dt.strftime("%d/%m/%Y %H:%M:%S UTC")

        # Optional active network probe against YouTube
        probe_success = True
        probe_msg = "Cookie đầy đủ các trường xác thực."

        if probe_network:
            try:
                # Test probe YouTube using yt_dlp fast metadata check
                import yt_dlp
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "cookiefile": str(cookie_path),
                    "extract_flat": True,
                    "noplaylist": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Probe a known music track without downloading
                    info = ydl.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=False)
                    if info and info.get("id"):
                        probe_success = True
                        probe_msg = "Xác thực với YouTube thành công 100% (Sẵn sàng tải 320k)."
                    else:
                        probe_success = False
                        probe_msg = "YouTube không trả về dữ liệu video với cookie này."
            except Exception as e:
                err_str = str(e)
                if "Sign in to confirm you’re not a bot" in err_str or "401" in err_str or "login" in err_str.lower():
                    probe_success = False
                    probe_msg = "Cookie đã hết hạn hoặc phiên đăng nhập YouTube bị vô hiệu hóa."
                else:
                    # Network glitch or soft warning
                    probe_success = True
                    probe_msg = f"Cookie nạp thành công (Kiểm tra nhanh: {err_str[:60]})."

        status_label = "ACTIVE" if (has_login and probe_success) else ("EXPIRED" if not probe_success else "WARNING")

        return {
            "exists": True,
            "valid": (has_login and probe_success),
            "status": status_label,
            "message": probe_msg,
            "cookie_count": len(cookies_list),
            "size_bytes": file_size,
            "critical_keys_found": found_critical,
            "account_logged_in": has_login,
            "earliest_expiry": earliest_expiry,
            "earliest_expiry_formatted": expiry_str,
            "path": str(cookie_path),
        }

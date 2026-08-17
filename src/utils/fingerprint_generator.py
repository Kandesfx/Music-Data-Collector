"""
Music Data Collector - Browser Fingerprint & Anti-Detection Spoofing Engine
Generates realistic desktop browser fingerprints (Chrome, Edge, Safari, Firefox)
along with matching Client Hints (Sec-CH-UA) and locale headers to bypass datacenter bot detection.
"""

import random
from typing import Dict, Any, Optional, List


class FingerprintGenerator:
    """
    Generates realistic, synchronized browser headers and client hints.
    """

    PROFILES = [
        {
            "name": "Chrome 131 on Windows 11 (Desktop)",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec_ch_ua_platform": '"Windows"',
            "sec_ch_ua_mobile": "?0",
            "platform": "Windows",
        },
        {
            "name": "Edge 131 on Windows 11 (Desktop)",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
            "sec_ch_ua": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec_ch_ua_platform": '"Windows"',
            "sec_ch_ua_mobile": "?0",
            "platform": "Windows",
        },
        {
            "name": "Chrome 130 on macOS (Desktop)",
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="130", "Chromium";v="130", "Not_A Brand";v="24"',
            "sec_ch_ua_platform": '"macOS"',
            "sec_ch_ua_mobile": "?0",
            "platform": "macOS",
        },
        {
            "name": "Firefox 133 on Windows 11 (Desktop)",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "sec_ch_ua": None,
            "sec_ch_ua_platform": None,
            "sec_ch_ua_mobile": None,
            "platform": "Windows",
        }
    ]

    DEFAULT_LANGUAGES = [
        "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en;q=0.6",
        "en-US,en;q=0.9,vi;q=0.8",
    ]

    @classmethod
    def get_random_profile(cls) -> Dict[str, Any]:
        """Return a random complete desktop browser profile."""
        return random.choice(cls.PROFILES)

    @classmethod
    def get_http_headers(
        cls,
        profile: Optional[Dict[str, Any]] = None,
        accept_type: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        custom_referer: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate complete HTTP headers matching a real desktop browser.
        """
        prof = profile or cls.PROFILES[0]  # Default to Chrome Windows 11
        headers = {
            "User-Agent": prof["user_agent"],
            "Accept": accept_type,
            "Accept-Language": random.choice(cls.DEFAULT_LANGUAGES),
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

        if prof.get("sec_ch_ua"):
            headers["Sec-CH-UA"] = prof["sec_ch_ua"]
            headers["Sec-CH-UA-Mobile"] = prof["sec_ch_ua_mobile"]
            headers["Sec-CH-UA-Platform"] = prof["sec_ch_ua_platform"]

        if custom_referer:
            headers["Referer"] = custom_referer

        return headers

    @classmethod
    def get_ytdlp_http_headers(cls) -> Dict[str, str]:
        """Generate headers specifically tuned for yt-dlp requests."""
        prof = cls.PROFILES[0]
        return {
            "User-Agent": prof["user_agent"],
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-CH-UA": prof["sec_ch_ua"],
            "Sec-CH-UA-Mobile": prof["sec_ch_ua_mobile"],
            "Sec-CH-UA-Platform": prof["sec_ch_ua_platform"],
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    @classmethod
    def get_ytdlp_extractor_args(cls) -> Dict[str, Any]:
        """
        Get optimal yt-dlp extractor args to avoid bot detection.
        Combines modern player clients with desktop browser spoofing.
        """
        return {
            "youtube": {
                "player_client": ["web", "mweb", "tv", "android", "ios"],
                "player_skip": ["webpage", "configs"],
            }
        }

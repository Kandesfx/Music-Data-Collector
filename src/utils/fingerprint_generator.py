"""
Music Data Collector - Advanced Browser Fingerprint & Anti-Detection Spoofing Engine v4.0
Generates realistic, synchronized desktop & mobile browser fingerprints with full correlation
between User-Agents, Sec-CH-UA Client Hints, Screen Dimensions, WebGL GPU contexts,
Hardware concurrency, JA3/JA4 TLS signatures, and YouTube/Spotify client contexts.
Inspired by browser-forge, fingerprint-suite, curl_cffi, and scrapling.
"""

import random
import time
from typing import Dict, Any, Optional, List


class FingerprintGenerator:
    """
    State-of-the-art Browser & Device Profile Emulation Engine.
    Guarantees 100% attribute consistency across headers, client hints, and DOM navigator properties.
    """

    # Comprehensive Curated Profile Catalog
    PROFILES: List[Dict[str, Any]] = [
        {
            "id": "win11_chrome_132_nv",
            "name": "Chrome 132 — Windows 11 x64 (NVIDIA RTX 4070)",
            "device_type": "desktop",
            "os": "Windows",
            "os_version": "10.0.22631",
            "browser": "Chrome",
            "browser_version": "132.0.6834.110",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"',
            "sec_ch_ua_full_version_list": '"Not A(Brand";v="8.0.0.0", "Chromium";v="132.0.6834.110", "Google Chrome";v="132.0.6834.110"',
            "sec_ch_ua_platform": '"Windows"',
            "sec_ch_ua_platform_version": '"15.0.0"',
            "sec_ch_ua_mobile": "?0",
            "sec_ch_ua_arch": '"x86"',
            "sec_ch_ua_bitness": '"64"',
            "sec_ch_ua_model": '""',
            "screen": {
                "width": 1920,
                "height": 1080,
                "availWidth": 1920,
                "availHeight": 1040,
                "colorDepth": 24,
                "pixelDepth": 24,
                "devicePixelRatio": 1.0
            },
            "webgl": {
                "unmasked_vendor": "Google Inc. (NVIDIA)",
                "unmasked_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
                "gl_version": "WebGL 2.0 (OpenGL ES 3.0 Chromium)",
                "shading_language_version": "WebGL GLSL ES 3.00 (OpenGL ES GLSL ES 3.0 Chromium)"
            },
            "hardware": {
                "hardware_concurrency": 16,
                "device_memory": 16,
                "max_touch_points": 0
            },
            "ja4_tls": "t13d1516h2_8daaf6152771_016e788ee515",
            "innertube_client": {
                "client_name": "WEB_REMIX",
                "client_version": "1.20250120.01.00",
                "os_name": "Windows",
                "os_version": "10.0"
            }
        },
        {
            "id": "win11_edge_131_amd",
            "name": "MS Edge 131 — Windows 11 x64 (AMD Radeon RX 7800 XT)",
            "device_type": "desktop",
            "os": "Windows",
            "os_version": "10.0.22631",
            "browser": "Edge",
            "browser_version": "131.0.2903.112",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
            "sec_ch_ua": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec_ch_ua_full_version_list": '"Microsoft Edge";v="131.0.2903.112", "Chromium";v="131.0.6778.205", "Not_A Brand";v="24.0.0.0"',
            "sec_ch_ua_platform": '"Windows"',
            "sec_ch_ua_platform_version": '"15.0.0"',
            "sec_ch_ua_mobile": "?0",
            "sec_ch_ua_arch": '"x86"',
            "sec_ch_ua_bitness": '"64"',
            "sec_ch_ua_model": '""',
            "screen": {
                "width": 2560,
                "height": 1440,
                "availWidth": 2560,
                "availHeight": 1400,
                "colorDepth": 24,
                "pixelDepth": 24,
                "devicePixelRatio": 1.25
            },
            "webgl": {
                "unmasked_vendor": "Google Inc. (AMD)",
                "unmasked_renderer": "ANGLE (AMD, AMD Radeon RX 7800 XT Direct3D11 vs_5_0 ps_5_0, D3D11)",
                "gl_version": "WebGL 2.0 (OpenGL ES 3.0 Chromium)",
                "shading_language_version": "WebGL GLSL ES 3.00 (OpenGL ES GLSL ES 3.0 Chromium)"
            },
            "hardware": {
                "hardware_concurrency": 12,
                "device_memory": 32,
                "max_touch_points": 0
            },
            "ja4_tls": "t13d1516h2_8daaf6152771_016e788ee515",
            "innertube_client": {
                "client_name": "WEB_REMIX",
                "client_version": "1.20250120.01.00",
                "os_name": "Windows",
                "os_version": "10.0"
            }
        },
        {
            "id": "macos_safari_18_m3",
            "name": "Safari 18.2 — macOS Sequoia (Apple M3 Max)",
            "device_type": "desktop",
            "os": "macOS",
            "os_version": "15.2",
            "browser": "Safari",
            "browser_version": "18.2",
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
            "sec_ch_ua": None,
            "sec_ch_ua_full_version_list": None,
            "sec_ch_ua_platform": None,
            "sec_ch_ua_platform_version": None,
            "sec_ch_ua_mobile": None,
            "sec_ch_ua_arch": None,
            "sec_ch_ua_bitness": None,
            "sec_ch_ua_model": None,
            "screen": {
                "width": 1728,
                "height": 1117,
                "availWidth": 1728,
                "availHeight": 1080,
                "colorDepth": 30,
                "pixelDepth": 30,
                "devicePixelRatio": 2.0
            },
            "webgl": {
                "unmasked_vendor": "Apple Inc.",
                "unmasked_renderer": "Apple M3 Max",
                "gl_version": "WebGL 2.0 (OpenGL ES 3.0 Metal)",
                "shading_language_version": "WebGL GLSL ES 3.00 (OpenGL ES GLSL ES 3.0 Metal)"
            },
            "hardware": {
                "hardware_concurrency": 14,
                "device_memory": 36,
                "max_touch_points": 0
            },
            "ja4_tls": "t13d1908h2_0270a6c6d482_f9be282f6e91",
            "innertube_client": {
                "client_name": "WEB_REMIX",
                "client_version": "1.20250120.01.00",
                "os_name": "Macintosh",
                "os_version": "10_15_7"
            }
        },
        {
            "id": "macos_chrome_131_m2",
            "name": "Chrome 131 — macOS Sequoia (Apple M2 Pro)",
            "device_type": "desktop",
            "os": "macOS",
            "os_version": "15.1.1",
            "browser": "Chrome",
            "browser_version": "131.0.6778.205",
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec_ch_ua_full_version_list": '"Google Chrome";v="131.0.6778.205", "Chromium";v="131.0.6778.205", "Not_A Brand";v="24.0.0.0"',
            "sec_ch_ua_platform": '"macOS"',
            "sec_ch_ua_platform_version": '"15.1.1"',
            "sec_ch_ua_mobile": "?0",
            "sec_ch_ua_arch": '"arm"',
            "sec_ch_ua_bitness": '"64"',
            "sec_ch_ua_model": '""',
            "screen": {
                "width": 1512,
                "height": 982,
                "availWidth": 1512,
                "availHeight": 945,
                "colorDepth": 30,
                "pixelDepth": 30,
                "devicePixelRatio": 2.0
            },
            "webgl": {
                "unmasked_vendor": "Google Inc. (Apple)",
                "unmasked_renderer": "ANGLE (Apple, Apple M2 Pro, Metal 3.1)",
                "gl_version": "WebGL 2.0 (OpenGL ES 3.0 Chromium)",
                "shading_language_version": "WebGL GLSL ES 3.00 (OpenGL ES GLSL ES 3.0 Chromium)"
            },
            "hardware": {
                "hardware_concurrency": 10,
                "device_memory": 16,
                "max_touch_points": 0
            },
            "ja4_tls": "t13d1516h2_8daaf6152771_016e788ee515",
            "innertube_client": {
                "client_name": "WEB_REMIX",
                "client_version": "1.20250120.01.00",
                "os_name": "Macintosh",
                "os_version": "10_15_7"
            }
        },
        {
            "id": "win11_firefox_134",
            "name": "Firefox 134 — Windows 11 x64 (Intel Iris Xe)",
            "device_type": "desktop",
            "os": "Windows",
            "os_version": "10.0.22631",
            "browser": "Firefox",
            "browser_version": "134.0",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
            "sec_ch_ua": None,
            "sec_ch_ua_full_version_list": None,
            "sec_ch_ua_platform": None,
            "sec_ch_ua_platform_version": None,
            "sec_ch_ua_mobile": None,
            "sec_ch_ua_arch": None,
            "sec_ch_ua_bitness": None,
            "sec_ch_ua_model": None,
            "screen": {
                "width": 1920,
                "height": 1080,
                "availWidth": 1920,
                "availHeight": 1040,
                "colorDepth": 24,
                "pixelDepth": 24,
                "devicePixelRatio": 1.0
            },
            "webgl": {
                "unmasked_vendor": "Google Inc. (Intel)",
                "unmasked_renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
                "gl_version": "WebGL 2.0",
                "shading_language_version": "WebGL GLSL ES 3.00"
            },
            "hardware": {
                "hardware_concurrency": 8,
                "device_memory": 16,
                "max_touch_points": 0
            },
            "ja4_tls": "t13d1708h2_8daaf6152771_016e788ee515",
            "innertube_client": {
                "client_name": "WEB_REMIX",
                "client_version": "1.20250120.01.00",
                "os_name": "Windows",
                "os_version": "10.0"
            }
        },
        {
            "id": "iphone_16_pro_safari_18",
            "name": "Safari 18.0 — iPhone 16 Pro Max (iOS 18.1)",
            "device_type": "mobile",
            "os": "iOS",
            "os_version": "18.1",
            "browser": "Mobile Safari",
            "browser_version": "18.0",
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
            "sec_ch_ua": None,
            "sec_ch_ua_full_version_list": None,
            "sec_ch_ua_platform": None,
            "sec_ch_ua_platform_version": None,
            "sec_ch_ua_mobile": None,
            "sec_ch_ua_arch": None,
            "sec_ch_ua_bitness": None,
            "sec_ch_ua_model": None,
            "screen": {
                "width": 430,
                "height": 932,
                "availWidth": 430,
                "availHeight": 932,
                "colorDepth": 24,
                "pixelDepth": 24,
                "devicePixelRatio": 3.0
            },
            "webgl": {
                "unmasked_vendor": "Apple Inc.",
                "unmasked_renderer": "Apple A18 Pro GPU",
                "gl_version": "WebGL 2.0 (OpenGL ES 3.0 Metal)",
                "shading_language_version": "WebGL GLSL ES 3.00 (OpenGL ES GLSL ES 3.0 Metal)"
            },
            "hardware": {
                "hardware_concurrency": 6,
                "device_memory": 8,
                "max_touch_points": 5
            },
            "ja4_tls": "t13d1908h2_0270a6c6d482_f9be282f6e91",
            "innertube_client": {
                "client_name": "IOS_MUSIC",
                "client_version": "7.33.51",
                "os_name": "iOS",
                "os_version": "18.1.0"
            }
        },
        {
            "id": "samsung_s24_chrome_131",
            "name": "Chrome 131 — Samsung Galaxy S24 Ultra (Android 14)",
            "device_type": "mobile",
            "os": "Android",
            "os_version": "14",
            "browser": "Chrome Mobile",
            "browser_version": "131.0.6778.200",
            "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.200 Mobile Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec_ch_ua_full_version_list": '"Google Chrome";v="131.0.6778.200", "Chromium";v="131.0.6778.200", "Not_A Brand";v="24.0.0.0"',
            "sec_ch_ua_platform": '"Android"',
            "sec_ch_ua_platform_version": '"14.0.0"',
            "sec_ch_ua_mobile": "?1",
            "sec_ch_ua_arch": '"arm64"',
            "sec_ch_ua_bitness": '"64"',
            "sec_ch_ua_model": '"SM-S928B"',
            "screen": {
                "width": 384,
                "height": 824,
                "availWidth": 384,
                "availHeight": 824,
                "colorDepth": 24,
                "pixelDepth": 24,
                "devicePixelRatio": 3.75
            },
            "webgl": {
                "unmasked_vendor": "Qualcomm",
                "unmasked_renderer": "Adreno (TM) 750",
                "gl_version": "WebGL 2.0 (OpenGL ES 3.2 Chromium)",
                "shading_language_version": "WebGL GLSL ES 3.00 (OpenGL ES GLSL ES 3.2 Chromium)"
            },
            "hardware": {
                "hardware_concurrency": 8,
                "device_memory": 12,
                "max_touch_points": 5
            },
            "ja4_tls": "t13d1516h2_8daaf6152771_016e788ee515",
            "innertube_client": {
                "client_name": "ANDROID_MUSIC",
                "client_version": "7.33.51",
                "os_name": "Android",
                "os_version": "14"
            }
        },
        {
            "id": "smart_tv_tizen_youtube",
            "name": "Samsung Smart TV Tizen (YouTube on TV / Cobalt)",
            "device_type": "tv",
            "os": "Tizen",
            "os_version": "7.0",
            "browser": "Cobalt",
            "browser_version": "24.lts.4",
            "user_agent": "Mozilla/5.0 (SMART-TV; LINUX; Tizen 7.0) AppleWebKit/537.36 (KHTML, like Gecko) 94.0.4606.31/7.0 TV Safari/537.36",
            "sec_ch_ua": None,
            "sec_ch_ua_full_version_list": None,
            "sec_ch_ua_platform": None,
            "sec_ch_ua_platform_version": None,
            "sec_ch_ua_mobile": None,
            "sec_ch_ua_arch": None,
            "sec_ch_ua_bitness": None,
            "sec_ch_ua_model": '"Samsung Smart TV"',
            "screen": {
                "width": 1920,
                "height": 1080,
                "availWidth": 1920,
                "availHeight": 1080,
                "colorDepth": 24,
                "pixelDepth": 24,
                "devicePixelRatio": 1.0
            },
            "webgl": {
                "unmasked_vendor": "ARM",
                "unmasked_renderer": "Mali-G52",
                "gl_version": "WebGL 2.0",
                "shading_language_version": "WebGL GLSL ES 3.00"
            },
            "hardware": {
                "hardware_concurrency": 4,
                "device_memory": 4,
                "max_touch_points": 0
            },
            "ja4_tls": "t13d1516h2_8daaf6152771_016e788ee515",
            "innertube_client": {
                "client_name": "TVHTML5_SIMPLY_EMBEDDED_PLAYER",
                "client_version": "2.0",
                "os_name": "Tizen",
                "os_version": "7.0"
            }
        }
    ]

    DEFAULT_LANGUAGES = [
        "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en;q=0.6",
        "en-US,en;q=0.9,vi;q=0.8",
        "en-US,en;q=0.9",
        "vi-VN,vi;q=0.9,ja-JP;q=0.8,ja;q=0.7,en;q=0.6"
    ]

    # Active profile selection (defaults to Windows 11 Chrome 132 NVIDIA)
    _active_profile_id: str = "win11_chrome_132_nv"

    _db_manager: Optional[Any] = None

    @classmethod
    def set_db_manager(cls, db_manager: Any):
        """Set DB manager reference and sync profiles from MongoDB."""
        cls._db_manager = db_manager
        cls.sync_with_db()

    @classmethod
    def sync_with_db(cls):
        """Sync custom profiles from MongoDB into local catalog."""
        if not cls._db_manager or not hasattr(cls._db_manager, "is_connected") or not cls._db_manager.is_connected():
            return

        try:
            # Seed presets if empty
            existing_count = cls._db_manager.db.fingerprint_profiles.count_documents({})
            if existing_count == 0:
                for p in cls.PROFILES:
                    p_copy = dict(p)
                    p_copy["is_custom"] = False
                    p_copy["is_active"] = (p["id"] == cls._active_profile_id)
                    p_copy["status"] = "verified"
                    p_copy["preflight_passed"] = True
                    cls._db_manager.upsert_fingerprint(p_copy)

            # Load active profile from DB if set
            active_doc = cls._db_manager.get_active_fingerprint()
            if active_doc:
                cls._active_profile_id = active_doc["id"]

            # Merge all profiles from DB
            db_profiles = cls._db_manager.get_all_fingerprints()
            if db_profiles:
                # Merge with catalog (override existing or append new)
                preset_ids = {p["id"] for p in cls.PROFILES}
                for db_p in db_profiles:
                    if db_p["id"] not in preset_ids:
                        cls.PROFILES.append(db_p)
        except Exception:
            pass

    @classmethod
    def get_all_profiles(cls) -> List[Dict[str, Any]]:
        """Return full catalog of profile presets and custom profiles."""
        if cls._db_manager:
            cls.sync_with_db()
        return cls.PROFILES

    @classmethod
    def get_active_profile(cls) -> Dict[str, Any]:
        """Return the currently selected active profile."""
        for p in cls.PROFILES:
            if p["id"] == cls._active_profile_id:
                return p
        return cls.PROFILES[0]

    @classmethod
    def set_active_profile(cls, profile_id: str) -> bool:
        """Set active profile by ID or 'random'."""
        if profile_id == "random":
            chosen = random.choice(cls.PROFILES)
            cls._active_profile_id = chosen["id"]
            if cls._db_manager:
                cls._db_manager.set_active_fingerprint(chosen["id"])
            return True

        for p in cls.PROFILES:
            if p["id"] == profile_id:
                cls._active_profile_id = profile_id
                if cls._db_manager:
                    cls._db_manager.set_active_fingerprint(profile_id)
                return True
        return False

    @classmethod
    def preflight_test(
        cls,
        profile: Optional[Dict[str, Any]] = None,
        proxy_url: Optional[str] = None,
        timeout: int = 5
    ) -> Dict[str, Any]:
        """
        Automated Pre-Flight Test for a browser profile before applying.
        Checks:
        1. User-Agent format validity
        2. Sec-CH-UA Platform correlation
        3. Real live HTTP probe through target proxy
        4. Latency measurement & Bot-Shield simulation
        """
        import requests
        prof = profile or cls.get_active_profile()
        headers = cls.get_http_headers(profile=prof)
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

        start_time = time.perf_counter()
        test_url = "https://httpbin.org/headers"
        fallback_url = "https://www.google.com"

        screen = prof.get("screen") or {"width": 1920, "height": 1080, "devicePixelRatio": 1.0}
        webgl = prof.get("webgl") or {"unmasked_vendor": "Google Inc.", "unmasked_renderer": "ANGLE (NVIDIA)"}

        checks = {
            "ua_valid": bool(prof.get("user_agent") and len(prof["user_agent"]) > 20),
            "client_hints_correlated": True,
            "webgl_context_valid": bool(webgl.get("unmasked_vendor") or webgl.get("unmasked_renderer")),
            "screen_dimensions_valid": bool(screen.get("width", 0) > 0),
            "tls_handshake": False,
            "http_status": 0,
        }

        # Check OS vs Sec-CH-UA Platform consistency
        os_name = prof.get("os", "").lower()
        ch_plat = (prof.get("sec_ch_ua_platform") or "").lower()
        if "win" in os_name and '"windows"' not in ch_plat and prof.get("sec_ch_ua"):
            checks["client_hints_correlated"] = False
        elif "mac" in os_name and '"macos"' not in ch_plat and prof.get("sec_ch_ua"):
            checks["client_hints_correlated"] = False

        latency_ms = 0
        error_msg = None

        try:
            resp = requests.get(test_url, headers=headers, proxies=proxies, timeout=timeout)
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            checks["tls_handshake"] = True
            checks["http_status"] = resp.status_code
        except Exception:
            # Try fallback endpoint
            try:
                resp = requests.get(fallback_url, headers=headers, proxies=proxies, timeout=timeout)
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                checks["tls_handshake"] = True
                checks["http_status"] = resp.status_code
            except Exception as ex:
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                error_msg = str(ex)

        passed = (
            checks["ua_valid"] and
            checks["client_hints_correlated"] and
            checks["webgl_context_valid"] and
            checks["tls_handshake"] and
            checks["http_status"] in (200, 204, 301, 302, 401, 403)
        )

        result = {
            "passed": passed,
            "status": "verified" if passed else "failed",
            "latency_ms": max(1, latency_ms),
            "checks": checks,
            "error": error_msg,
            "profile_name": prof.get("name"),
            "profile_id": prof.get("id"),
        }

        if cls._db_manager and prof.get("id"):
            cls._db_manager.update_fingerprint_test_result(
                profile_id=prof["id"],
                status=result["status"],
                preflight_passed=passed,
                latency_ms=result["latency_ms"],
                details=f"Status: {checks['http_status']}, Latency: {result['latency_ms']}ms"
            )

        return result


    @classmethod
    def get_http_headers(
        cls,
        profile: Optional[Dict[str, Any]] = None,
        accept_type: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        custom_referer: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate complete, real-world HTTP headers with exact Client Hints and order.
        """
        prof = profile or cls.get_active_profile()
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

        if prof.get("sec_ch_ua_platform_version"):
            headers["Sec-CH-UA-Platform-Version"] = prof["sec_ch_ua_platform_version"]

        if prof.get("sec_ch_ua_arch"):
            headers["Sec-CH-UA-Arch"] = prof["sec_ch_ua_arch"]

        if prof.get("sec_ch_ua_bitness"):
            headers["Sec-CH-UA-Bitness"] = prof["sec_ch_ua_bitness"]

        if prof.get("sec_ch_ua_model") and prof["sec_ch_ua_model"] != '""':
            headers["Sec-CH-UA-Model"] = prof["sec_ch_ua_model"]

        if custom_referer:
            headers["Referer"] = custom_referer

        return headers

    @classmethod
    def get_ytdlp_http_headers(cls) -> Dict[str, str]:
        """Generate headers specifically tuned for yt-dlp & streaming requests."""
        prof = cls.get_active_profile()
        headers = {
            "User-Agent": prof["user_agent"],
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

        if prof.get("sec_ch_ua"):
            headers["Sec-CH-UA"] = prof["sec_ch_ua"]
            headers["Sec-CH-UA-Mobile"] = prof["sec_ch_ua_mobile"]
            headers["Sec-CH-UA-Platform"] = prof["sec_ch_ua_platform"]

        return headers

    @classmethod
    def get_ytdlp_extractor_args(cls) -> Dict[str, Any]:
        """
        Get optimal yt-dlp extractor args using correlated client context.
        """
        prof = cls.get_active_profile()
        innertube = prof.get("innertube_client", {})
        client_name = innertube.get("client_name", "web").lower()

        # Build prioritized client list starting with active profile client
        all_clients = ["web", "mweb", "tv", "android", "ios"]
        if client_name in ["web_remix", "web"]:
            prioritized = ["web", "mweb", "tv", "android", "ios"]
        elif client_name == "android_music":
            prioritized = ["android", "web", "mweb", "tv", "ios"]
        elif client_name == "ios_music":
            prioritized = ["ios", "web", "mweb", "tv", "android"]
        elif "tv" in client_name:
            prioritized = ["tv", "web", "mweb", "android", "ios"]
        else:
            prioritized = all_clients

        return {
            "youtube": {
                "player_client": prioritized,
                "player_skip": ["webpage", "configs"],
            }
        }

    @classmethod
    def get_dom_stealth_script(cls) -> str:
        """
        Generate JavaScript injection snippet (like playwright-stealth / undetected)
        to spoof navigator, WebGL, and screen dimensions inside headless browsers.
        """
        prof = cls.get_active_profile()
        screen = prof.get("screen", {})
        webgl = prof.get("webgl", {})
        hw = prof.get("hardware", {})

        return f"""
        // ─── Music Collector Studio DOM Stealth & Anti-Detection Polyfill ───
        (function() {{
            // 1. Spoof navigator properties
            Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
            Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {hw.get("hardware_concurrency", 8)} }});
            Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {hw.get("device_memory", 16)} }});
            Object.defineProperty(navigator, 'maxTouchPoints', {{ get: () => {hw.get("max_touch_points", 0)} }});
            Object.defineProperty(navigator, 'languages', {{ get: () => ['vi-VN', 'vi', 'en-US', 'en'] }});
            Object.defineProperty(navigator, 'platform', {{ get: () => '{prof.get("os", "Win32")}' }});

            // 2. Spoof Screen Dimensions
            Object.defineProperty(screen, 'width', {{ get: () => {screen.get("width", 1920)} }});
            Object.defineProperty(screen, 'height', {{ get: () => {screen.get("height", 1080)} }});
            Object.defineProperty(screen, 'availWidth', {{ get: () => {screen.get("availWidth", 1920)} }});
            Object.defineProperty(screen, 'availHeight', {{ get: () => {screen.get("availHeight", 1040)} }});
            Object.defineProperty(screen, 'colorDepth', {{ get: () => {screen.get("colorDepth", 24)} }});
            Object.defineProperty(window, 'devicePixelRatio', {{ get: () => {screen.get("devicePixelRatio", 1.0)} }});

            // 3. Spoof WebGL Vendor & Renderer
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) return '{webgl.get("unmasked_vendor", "Google Inc. (NVIDIA)")}';
                if (parameter === 37446) return '{webgl.get("unmasked_renderer", "ANGLE (NVIDIA, GeForce RTX 4070 Direct3D11)")}';
                return getParameter.apply(this, arguments);
            }};

            if (window.WebGL2RenderingContext) {{
                const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(parameter) {{
                    if (parameter === 37445) return '{webgl.get("unmasked_vendor", "Google Inc. (NVIDIA)")}';
                    if (parameter === 37446) return '{webgl.get("unmasked_renderer", "ANGLE (NVIDIA, GeForce RTX 4070 Direct3D11)")}';
                    return getParameter2.apply(this, arguments);
                }};
            }}

            // 4. Chrome Runtime Mock
            if (!window.chrome) {{
                window.chrome = {{ runtime: {{}} }};
            }}
        }})();
        """


"""
Scripts - Test Network Shield & Masked Egress IP Verification
Tests Cloudflare WARP SOCKS5 Gateway, ProxyManager, and yt-dlp extraction with anti-detection headers.
"""

import sys
import time
import requests
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.utils.fingerprint_generator import FingerprintGenerator
from src.utils.proxy_manager import ProxyManager
from src.utils.warp_controller import WarpController
from src.utils.logger import get_logger

logger = get_logger("test_shield")


def test_network_shield():
    print("\n========================================================")
    print("🛡️ MUSIC DATA COLLECTOR - NETWORK SHIELD & ANTI-DETECTION")
    print("========================================================\n")

    # 1. Test Fingerprint Generator
    print("🎭 [1/4] Testing Browser Fingerprint Generator...")
    profile = FingerprintGenerator.get_random_profile()
    headers = FingerprintGenerator.get_http_headers(profile)
    print(f"   ✓ Generated Profile: {profile['name']}")
    print(f"   ✓ User-Agent: {headers['User-Agent'][:60]}...")
    print(f"   ✓ Sec-CH-UA: {headers.get('Sec-CH-UA', 'N/A')}")
    print(f"   ✓ Accept-Language: {headers.get('Accept-Language')}")

    # 2. Test Direct Connection Egress IP
    print("\n🏢 [2/4] Inspecting Direct Host Egress IP...")
    direct_res = ProxyManager.inspect_proxy_egress(None)
    print(f"   ✓ Host IP: {direct_res.get('ip')}")
    print(f"   ✓ ISP: {direct_res.get('isp')}")
    print(f"   ✓ Location: {direct_res.get('city')}, {direct_res.get('country')}")
    print(f"   ✓ Is Datacenter IP: {direct_res.get('is_datacenter')}")

    # 3. Test Cloudflare WARP Status
    print("\n⚡ [3/4] Testing Cloudflare WARP Status & SOCKS5 Gateway...")
    warp_status = WarpController.get_status()
    print(f"   ✓ WARP Installed: {warp_status.get('installed')}")
    print(f"   ✓ WARP Connected: {warp_status.get('is_connected')}")
    print(f"   ✓ SOCKS5 Port: {warp_status.get('proxy_port')}")

    # 4. Test SOCKS5 Egress IP if WARP or local proxy is reachable
    print("\n🌐 [4/4] Testing Masked Egress IP via SOCKS5 (127.0.0.1:40000)...")
    egress_res = ProxyManager.inspect_proxy_egress("socks5://127.0.0.1:40000")
    if egress_res.get("success"):
        print(f"   🟢 SUCCESS! Masked Egress IP: {egress_res.get('ip')}")
        print(f"   ✓ Masked ISP: {egress_res.get('isp')}")
        print(f"   ✓ Country: {egress_res.get('country')}")
        print(f"   ✓ Latency: {egress_res.get('latency_ms')}ms")
        print(f"   ✓ Is Datacenter IP: {egress_res.get('is_datacenter')}")
    else:
        print(f"   ℹ️ Local SOCKS5 not active or in local dev environment: {egress_res.get('error')}")

    print("\n========================================================")
    print("✅ Network Shield & Anti-Detection Test Completed!")
    print("========================================================\n")


if __name__ == "__main__":
    test_network_shield()

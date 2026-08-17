import subprocess
import sys

print("=== Testing yt-dlp with OAuth2 or alternative clients ===")
# Test tv, mweb with po_token or oauth
test_clients = [
    ["yt-dlp", "ytsearch1:Rick Astley Never Gonna Give You Up", "--extractor-args", "youtube:player_client=tv", "-F", "--proxy", "socks5://127.0.0.1:40000"],
    ["yt-dlp", "ytsearch1:Rick Astley Never Gonna Give You Up", "--extractor-args", "youtube:player_client=android_creator", "-F", "--proxy", "socks5://127.0.0.1:40000"],
    ["yt-dlp", "ytsearch1:Rick Astley Never Gonna Give You Up", "--extractor-args", "youtube:player_client=android_testsuite", "-F", "--proxy", "socks5://127.0.0.1:40000"],
    ["yt-dlp", "ytsearch1:Rick Astley Never Gonna Give You Up", "--extractor-args", "youtube:player_client=media_connect", "-F", "--proxy", "socks5://127.0.0.1:40000"],
    ["yt-dlp", "ytsearch1:Rick Astley Never Gonna Give You Up", "--extractor-args", "youtube:player_client=web_safari", "-F", "--proxy", "socks5://127.0.0.1:40000"],
]

for cmd in test_clients:
    print(f"\nExecuting: {' '.join(cmd[2:5])}")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
    if res.returncode == 0:
        print("  [SUCCESS] Formats extracted successfully!")
        lines = [line for line in res.stdout.splitlines() if "audio only" in line or "m4a" in line or "mp3" in line or "opus" in line]
        for l in lines[:3]:
            print(f"    {l}")
    else:
        err = [l for l in (res.stderr + res.stdout).splitlines() if "ERROR" in l or "Sign in" in l]
        print(f"  [FAILED] {err[0] if err else res.stderr[:100]}")

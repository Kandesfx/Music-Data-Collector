from pathlib import Path
import yt_dlp

cookie_path = Path("config/cookies.txt")
sanitized_path = Path("/tmp/sanitized_cookies.txt")

# Filter out transient / rotating timestamp tokens (PSIDTS, SIDCC)
excluded_keys = {"__Secure-1PSIDTS", "__Secure-3PSIDTS", "SIDCC", "__Secure-1PSIDCC", "__Secure-3PSIDCC", "YSC"}

with open(cookie_path, "r", encoding="utf-8") as f_in, open(sanitized_path, "w", encoding="utf-8") as f_out:
    for line in f_in:
        if line.startswith("#"):
            f_out.write(line)
            continue
        parts = line.strip().split("\t")
        if len(parts) >= 7:
            key_name = parts[5]
            if key_name not in excluded_keys:
                f_out.write(line)

print("Sanitized cookies written. Testing with yt-dlp...")

opts = {
    "format": "bestaudio/best",
    "cookiefile": str(sanitized_path),
    "proxy": "socks5://127.0.0.1:40000",
    "quiet": False,
    "no_warnings": False,
    "noplaylist": True,
    "socket_timeout": 30,
}

try:
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info("ytsearch1:Smooth Criminal Michael Jackson", download=False)
        print(f"[SUCCESS] Extracted: {info['entries'][0]['title']}")
except Exception as e:
    print(f"[FAILED] Error: {e}")

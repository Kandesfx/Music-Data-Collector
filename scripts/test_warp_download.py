import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import yt_dlp

cookie_file = str(BASE_DIR / "config" / "cookies.txt")
query = "ytsearch1:Smooth Criminal Michael Jackson"
out_dir = Path("/tmp/test_warp_dl")
out_dir.mkdir(parents=True, exist_ok=True)
out_template = str(out_dir / "audio.%(ext)s")

opts = {
    "format": "bestaudio/best",
    "outtmpl": out_template,
    "cookiefile": cookie_file,
    "proxy": "socks5://127.0.0.1:40000",
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }
    ],
    "quiet": False,
    "no_warnings": False,
    "noplaylist": True,
    "socket_timeout": 30,
}

print("=== Testing yt-dlp download via Cloudflare WARP ===")
try:
    with yt_dlp.YoutubeDL(opts) as ydl:
        res = ydl.download([query])
    files = list(out_dir.glob("*.mp3"))
    print(f"[SUCCESS] Download completed! Exit code: {res}, Files: {files}")
except Exception as e:
    print(f"[FAILED] Error: {e}")

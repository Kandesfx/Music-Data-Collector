import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import yt_dlp

query = "ytsearch1:Smooth Criminal Michael Jackson"
out_dir = Path("/tmp/test_no_cookie_dl")
out_dir.mkdir(parents=True, exist_ok=True)
out_template = str(out_dir / "audio.%(ext)s")

# Test 1: No cookies, WARP proxy, android client
print("=== Test 1: No cookies with android/web client via WARP ===")
opts1 = {
    "format": "bestaudio/best",
    "outtmpl": out_template,
    "proxy": "socks5://127.0.0.1:40000",
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "web"],
        }
    },
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

try:
    with yt_dlp.YoutubeDL(opts1) as ydl:
        res = ydl.download([query])
    files = list(out_dir.glob("*.mp3"))
    print(f"[SUCCESS Test 1] Result: {res}, Files: {files}")
except Exception as e:
    print(f"[FAILED Test 1] Error: {e}")

# Test 2: spotDL download
print("\n=== Test 2: spotDL download via CLI ===")
import subprocess
try:
    cmd = [
        sys.executable, "-m", "spotdl", "download", "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
        "--output", "/tmp/test_no_cookie_dl",
        "--format", "mp3",
        "--bitrate", "320k",
        "--headless",
    ]
    res2 = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
    print("spotDL returncode:", res2.returncode)
    print("spotDL stdout:", res2.stdout[:300])
    print("spotDL stderr:", res2.stderr[:300])
    files = list(out_dir.glob("*.mp3"))
    print(f"Files in output dir: {files}")
except Exception as e:
    print(f"[FAILED Test 2] Error: {e}")

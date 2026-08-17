import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import yt_dlp

print("=== Testing PO-Token Automated Provider in yt-dlp ===")
out_dir = Path("/tmp/test_pot_dl")
out_dir.mkdir(parents=True, exist_ok=True)
out_template = str(out_dir / "audio.%(ext)s")

query = "ytsearch1:Smooth Criminal Michael Jackson"

opts = {
    "format": "bestaudio/best",
    "outtmpl": out_template,
    "extractor_args": {
        "youtube": {
            "player_client": ["web", "mweb"],
            "po_token": ["web+auto", "mweb+auto"],
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
    with yt_dlp.YoutubeDL(opts) as ydl:
        res = ydl.download([query])
    files = list(out_dir.glob("*.mp3"))
    print(f"[SUCCESS] Download completed! Exit code: {res}, Files: {[f.name for f in files]}")
    for f in files:
        print(f"  File: {f.name}, Size: {f.stat().st_size / 1024 / 1024:.2f} MB")
except Exception as e:
    print(f"[FAILED] Error: {e}")

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import yt_dlp
from src.downloaders.download_manager import DownloadManager
from src.storage.db_manager import DBManager
from src.storage.file_manager import FileManager
from src.utils.session_manager import SessionManager
from src.utils.proxy_manager import ProxyManager
from src.utils.health_checker import HealthChecker

print("=== Testing Real Download with Android Creator & Multi-Client Strategy ===")
out_dir = Path("/tmp/test_real_mp3")
out_dir.mkdir(parents=True, exist_ok=True)
out_template = str(out_dir / "audio.%(ext)s")

query = "ytsearch1:Smooth Criminal Michael Jackson"
opts = {
    "format": "bestaudio/best",
    "outtmpl": out_template,
    "extractor_args": {
        "youtube": {
            "player_client": ["android_creator", "android_testsuite", "media_connect", "web_safari", "tv", "web"],
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
    print(f"[SUCCESS] Download completed! Exit code: {res}, Created files: {[f.name for f in files]}")
    for f in files:
        print(f"  File: {f.name}, Size: {f.stat().st_size / 1024 / 1024:.2f} MB")
except Exception as e:
    print(f"[FAILED] Error: {e}")

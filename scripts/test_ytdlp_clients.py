import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import yt_dlp

cookie_file = str(BASE_DIR / "config" / "cookies.txt")
query = "ytsearch1:Smooth Criminal Michael Jackson"
out_template = "/tmp/test_audio.%(ext)s"

clients_to_test = [
    ("Default (No extractor_args)", None),
    ("web_remix,web", {"youtube": {"player_client": ["web_remix", "web"]}}),
    ("android,web", {"youtube": {"player_client": ["android", "web"]}}),
    ("mweb", {"youtube": {"player_client": ["mweb"]}}),
    ("web with cookies", {"youtube": {"player_client": ["web"]}}),
    ("tv_embedded", {"youtube": {"player_client": ["tv_embedded"]}}),
    ("ios", {"youtube": {"player_client": ["ios"]}}),
]

for label, ext_args in clients_to_test:
    print(f"\n--- Testing Client: {label} ---")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "cookiefile": cookie_file,
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
        "socket_timeout": 15,
    }
    if ext_args:
        opts["extractor_args"] = ext_args
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if info:
                title = info.get("title") or (info.get("entries", [{}])[0].get("title") if "entries" in info else "Unknown")
                print(f"  [SUCCESS] Extracted: {title}")
    except Exception as e:
        print(f"  [FAILED] Error: {e}")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yt_dlp
from src.utils.fingerprint_generator import FingerprintGenerator
from src.downloaders.download_manager import DownloadManager

def main():
    print("Testing yt-dlp through Cloudflare WARP SOCKS5 Gateway (127.0.0.1:40000)...")
    dm = DownloadManager()
    cookie_file = dm._get_active_cookie_file()
    print(f"Active cookie file: {cookie_file}")

    ydl_opts = {
        "format": "bestaudio/best",
        "proxy": "socks5://127.0.0.1:40000",
        "extractor_args": FingerprintGenerator.get_ytdlp_extractor_args(),
        "http_headers": FingerprintGenerator.get_ytdlp_http_headers(),
        "quiet": False,
        "noplaylist": True,
    }
    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info("ytsearch1:Sơn Tùng M-TP Đừng Làm Trái Tim Anh Đau", download=False)
        entries = info.get("entries", [info])
        if entries:
            first = entries[0]
            print(f"🎉 SUCCESS! Found Track: {first.get('title')} (ID: {first.get('id')}) via Cloudflare WARP!")

if __name__ == "__main__":
    main()

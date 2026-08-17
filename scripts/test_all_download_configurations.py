import os
import sys
import time
import subprocess
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
from src.collectors.lyrics_collector import LyricsCollector
from src.utils.fingerprint_generator import FingerprintGenerator

print("=" * 60)
print("🚀 COMPREHENSIVE DOWNLOAD & PIPELINE CAPABILITY TEST MATRIX")
print("=" * 60)

test_track = {
    "spotify_id": "test_matrix_track_1",
    "name": "Nang Am Xa Dan",
    "artist_name": "Son Tung M-TP",
    "album_name": "Nang Am Xa Dan (Single)",
    "duration_ms": 204000,
    "image_url": "https://i.scdn.co/image/ab67616d0000b273b320d3eb84e2ffcfaeb2f99d",
}

# ─── 1. Test Lyrics Collector ────────────────────────────────
print("\n[1/5] Testing Synced Lyrics & Plain Lyrics Engine (LRCLIB)...")
lyrics = LyricsCollector.fetch_lyrics(
    track_name=test_track["name"],
    artist_name=test_track["artist_name"],
    duration_ms=test_track["duration_ms"],
)
if lyrics and (lyrics.get("synced_lyrics") or lyrics.get("plain_lyrics")):
    has_synced = bool(lyrics.get("synced_lyrics"))
    print(f"  ✅ Lyrics Fetch SUCCESS! Synced .lrc: {has_synced}, Length: {len(lyrics.get('plain_lyrics', '') or lyrics.get('synced_lyrics', ''))} chars")
else:
    print("  ⚠️ Lyrics not found for sample (acceptable for rare tracks, testing plain search)")

# ─── 2. Test Multiple yt-dlp Client Configurations ──────────
configs_to_test = [
    {
        "name": "A. Android Music Client + WARP SOCKS5 (No Cookies)",
        "extractor_args": {"youtube": {"player_client": ["android", "mweb"]}},
        "proxy": "socks5://127.0.0.1:40000",
        "cookiefile": None,
    },
    {
        "name": "B. TV Client + WARP SOCKS5 (No Cookies)",
        "extractor_args": {"youtube": {"player_client": ["tv"]}},
        "proxy": "socks5://127.0.0.1:40000",
        "cookiefile": None,
    },
    {
        "name": "C. Web Remix (YouTube Music) + WARP SOCKS5",
        "extractor_args": {"youtube": {"player_client": ["web_remix", "web"]}},
        "proxy": "socks5://127.0.0.1:40000",
        "cookiefile": None,
    },
    {
        "name": "D. Direct Connection with Android/TV Client",
        "extractor_args": {"youtube": {"player_client": ["android", "tv"]}},
        "proxy": None,
        "cookiefile": None,
    },
    {
        "name": "E. Web + Cookies + WARP SOCKS5",
        "extractor_args": {"youtube": {"player_client": ["web"]}},
        "proxy": "socks5://127.0.0.1:40000",
        "cookiefile": str(BASE_DIR / "config" / "cookies.txt"),
    },
]

results = []
query = f"ytsearch1:{test_track['artist_name']} - {test_track['name']}"

for idx, cfg in enumerate(configs_to_test, 1):
    print(f"\n[2/5] Testing Config {cfg['name']}...")
    out_dir = Path(f"/tmp/test_matrix_dl_{idx}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(out_dir / "audio.%(ext)s")

    opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
    }
    if cfg.get("extractor_args"):
        opts["extractor_args"] = cfg["extractor_args"]
    if cfg.get("proxy"):
        opts["proxy"] = cfg["proxy"]
    if cfg.get("cookiefile") and Path(cfg["cookiefile"]).exists():
        opts["cookiefile"] = cfg["cookiefile"]

    t0 = time.time()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([query])
        mp3_files = list(out_dir.glob("*.mp3"))
        elapsed = round(time.time() - t0, 2)
        if mp3_files:
            file_size_mb = mp3_files[0].stat().st_size / (1024 * 1024)
            print(f"  ✅ SUCCESS in {elapsed}s! File: {mp3_files[0].name} ({file_size_mb:.2f} MB)")
            results.append({"config": cfg["name"], "success": True, "elapsed": elapsed, "size_mb": file_size_mb})
        else:
            print(f"  ❌ FAILED: No MP3 generated in {elapsed}s")
            results.append({"config": cfg["name"], "success": False, "error": "No file created"})
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        err_msg = str(e)
        first_err = err_msg.splitlines()[-1] if err_msg else "Unknown error"
        print(f"  ❌ FAILED in {elapsed}s: {first_err}")
        results.append({"config": cfg["name"], "success": False, "error": first_err})

# ─── 3. Test Full DownloadManager Pipeline ──────────────────
print("\n[3/5] Testing Full Integrated DownloadManager with winning strategy...")
db = DBManager()
fm = FileManager()
sm = SessionManager()
pm = ProxyManager(db_manager=db)
hc = HealthChecker()
dm = DownloadManager(db, fm, sm, hc, pm)

ok, final_path, method = dm.download_track(test_track)
print(f"  Result: success={ok}, method={method}, path={final_path}")

print("\n" + "=" * 60)
print("📊 FINAL SUMMARY MATRIX:")
print("=" * 60)
for r in results:
    status_icon = "✅ PASSED" if r["success"] else "❌ FAILED"
    info = f"({r.get('elapsed')}s, {r.get('size_mb', 0):.2f}MB)" if r["success"] else f"({r.get('error')})"
    print(f"{status_icon} | {r['config']} {info}")
print(f"\nIntegrated DownloadManager Result: {'✅ PASSED' if ok else '❌ FAILED'}")

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.downloaders.download_manager import DownloadManager

dm = DownloadManager()
track = {
    "name": "Bật Nhạc Lên",
    "artist_name": "HIEUTHUHAI, Harmonie",
    "duration_ms": 204000,
    "spotify_id": "test_bat_nhac_len"
}

print("1. Matching video via dm.matcher...")
candidates = dm.matcher.find_candidates_ranked(track["artist_name"], track["name"], track["duration_ms"])
print(f"Found {len(candidates)} candidates:")
for c in candidates:
    print(" -", c)

if candidates:
    url = candidates[0].get("youtube_url")
    print(f"\n2. Testing yt-dlp download for: {url}...")
    temp_dir = dm.fm.create_temp_dir()
    ok, path, err = dm._download_ytdlp(url, temp_dir)
    print("Download OK:", ok, "Path:", path, "\nError:", err)

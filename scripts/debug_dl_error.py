import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.downloaders.ytmusic_matcher import YTMusicMatcher
from src.downloaders.download_manager import DownloadManager

dm = DownloadManager()
track = {
    "name": "Bật Nhạc Lên",
    "artist_name": "HIEUTHUHAI, Harmonie",
    "duration_ms": 204000,
    "spotify_id": "test_bat_nhac_len"
}

print("1. Matching video...")
res = YTMusicMatcher.find_best_match(track["name"], track["artist_name"], track["duration_ms"])
print("Match result:", res)

if res.get("match_found"):
    url = res.get("url")
    print(f"2. Testing yt-dlp download for: {url}...")
    temp_dir = dm.fm.create_temp_dir()
    ok, path, err = dm._download_ytdlp(url, temp_dir)
    print("Download OK:", ok, "Path:", path, "Error:", err)

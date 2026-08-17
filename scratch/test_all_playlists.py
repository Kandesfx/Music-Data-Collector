import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.collectors.spotify_collector import SpotifyCollector
from src.collectors.trend_manager import TrendManager

c = SpotifyCollector()
tm = TrendManager()
playlists = tm._get_trending_playlists()

results = []
for pl in playlists:
    title = pl["title"]
    query = pl["query"]
    mode = pl.get("mode", "playlist")
    tracks = c.collect_custom(mode=mode, query=query, max_tracks=50, default_genre=pl.get("genre"))
    results.append(f"[{title}] (mode={mode}) -> Found {len(tracks)} tracks")
    if tracks:
        results.append(f"   First track: {tracks[0]['name']} - {tracks[0]['artist_name']}")

print("\n".join(results).encode("ascii", "replace").decode("ascii"))

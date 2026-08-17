import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.collectors.spotify_collector import SpotifyCollector

c = SpotifyCollector()
pl_url = "https://open.spotify.com/playlist/37i9dQZEVXbLdGSmz6xilI"
res = c.collect_playlist_tracks(pl_url, max_tracks=50)
print(f"Top 50 VN playlist result: {len(res)} tracks")
for i, t in enumerate(res[:5], 1):
    print(f"  {i}. {t['name']} - {t['artist_name']}")

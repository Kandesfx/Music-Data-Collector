import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.collectors.spotify_collector import SpotifyCollector

c = SpotifyCollector()
res = c.collect_custom(mode="search", query="LoiChoi", max_tracks=50)
print(f"✅ Live Tracks found for 'LoiChoi' (limit: 50): {len(res)} bài")
for i, t in enumerate(res[:10], 1):
    print(f"  {i}. {t['name']} - {t['artist_name']} ({t.get('duration_formatted', '0:00')})")

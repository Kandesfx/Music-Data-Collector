import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.collectors.spotify_collector import SpotifyCollector

c = SpotifyCollector()
res = c.collect_custom(mode="album", query="LoiChoi", max_tracks=50)
print(f"Tracks found for 'LoiChoi' with mode=album (limit=50): {len(res)}")
for i, t in enumerate(res[:5], 1):
    print(f"{i}. {t['name']}")

res2 = c.collect_custom(mode="search", query="LoiChoi", max_tracks=50)
print(f"\nTracks found for 'LoiChoi' with mode=search (limit=50): {len(res2)}")
for i, t in enumerate(res2[:5], 1):
    print(f"{i}. {t['name']}")

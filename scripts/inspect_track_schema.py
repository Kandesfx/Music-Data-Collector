import sys
import json
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.storage.db_manager import DBManager
db = DBManager()

track = db.db.tracks.find_one({"download_status": "completed"}, {"_id": 0})
if not track:
    track = db.db.tracks.find_one({}, {"_id": 0})

print("Sample track schema:")
print(json.dumps(track, indent=2, default=str))

# Summary of stats
total = db.db.tracks.count_documents({})
with_pop = db.db.tracks.count_documents({"popularity": {"$exists": True, "$ne": None}})
with_views = db.db.tracks.count_documents({"youtube_views": {"$exists": True}})
print(f"\nStats across {total} tracks:")
print(f" - With popularity: {with_pop}")
print(f" - With youtube_views: {with_views}")

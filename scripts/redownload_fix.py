import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.storage.db_manager import DBManager
from src.downloaders.download_manager import DownloadManager

def run_fix():
    db = DBManager()
    if not db.is_connected():
        print("Could not connect to database.")
        return

    docs = list(db.db["tracks"].find({"name": {"$regex": "1-800-LOVE", "$options": "i"}}))
    print(f"Found {len(docs)} matching tracks.")

    dm = DownloadManager(db_manager=db)

    for doc in docs:
        sp_id = doc.get("spotify_id")
        old_path = doc.get("local_path")
        print(f"\nProcessing Track: {doc.get('name')} by {doc.get('artist_name')} ({sp_id})")
        print(f"Old local path: {old_path}")

        # Remove old cached audio file to force re-download
        if old_path:
            full_old = BASE_DIR / old_path
            if full_old.exists():
                try:
                    full_old.unlink()
                    print(f"Deleted old mismatched file: {full_old}")
                except Exception as e:
                    print(f"Could not delete old file: {e}")

        # Reset download status in DB to force fresh download
        db.db["tracks"].update_one(
            {"spotify_id": sp_id},
            {"$set": {"download_status": "pending", "local_path": None, "file_size_bytes": 0}}
        )

        # Run fresh download with upgraded matcher
        ok, final_path, method = dm.download_track(doc)
        print(f"Re-download result: success={ok}, path={final_path}, method={method}")

        updated_doc = db.db["tracks"].find_one({"spotify_id": sp_id})
        print(f"Updated DB status: {updated_doc.get('download_status')}, path: {updated_doc.get('local_path')}")

if __name__ == "__main__":
    run_fix()

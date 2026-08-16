"""
Migrate track tags in MongoDB: set added_by and ingest_type for all tracks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.db_manager import DBManager


def main():
    db = DBManager()
    if not db.is_connected():
        print("Could not connect to MongoDB.")
        return

    # Update completed tracks
    r1 = db.db.tracks.update_many(
        {"download_status": "completed"},
        {"$set": {"added_by": "admin", "ingest_type": "full_audio"}}
    )

    # Update pending / failed tracks
    r2 = db.db.tracks.update_many(
        {"download_status": {"$ne": "completed"}},
        {"$set": {"added_by": "admin", "ingest_type": "metadata_only"}}
    )

    print(f"Migration finished. Updated completed: {r1.modified_count}, metadata-only: {r2.modified_count}")


if __name__ == "__main__":
    main()

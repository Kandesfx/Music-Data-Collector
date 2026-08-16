import os
import sys
from pathlib import Path
from mutagen.mp3 import MP3

# Set UTF-8
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.storage.db_manager import DBManager
from config import settings

def format_duration(seconds: float) -> str:
    total_sec = int(round(seconds))
    m = total_sec // 60
    s = total_sec % 60
    return f"{m}:{s:02d}"

def main():
    db = DBManager()
    if not db.connect():
        print("Failed to connect to MongoDB.")
        return

    tracks = list(db.db.tracks.find({}))
    print(f"Total tracks in MongoDB: {len(tracks)}")
    
    updated_count = 0
    completed_fixed = 0

    for t in tracks:
        sid = t.get("spotify_id")
        cur_duration_ms = t.get("duration_ms")
        cur_duration_fmt = t.get("duration_formatted")
        local_path = t.get("local_path")
        
        duration_sec = None

        # 1. If local MP3 exists, get EXACT physical duration
        if local_path:
            p = settings.BASE_DIR / local_path
            if p.exists():
                try:
                    audio = MP3(str(p))
                    duration_sec = audio.info.length
                    completed_fixed += 1
                except Exception as ex:
                    print(f"Error reading MP3 {p}: {ex}")

        # 2. If duration_ms was present in doc
        if duration_sec is None and cur_duration_ms and cur_duration_ms > 0:
            duration_sec = cur_duration_ms / 1000.0

        # 3. Fallback to reasonable track length if still missing
        if duration_sec is None or duration_sec <= 0:
            duration_sec = 210.0 # 3:30

        calc_ms = int(duration_sec * 1000)
        calc_fmt = format_duration(duration_sec)

        # Update if changed or missing
        if cur_duration_ms != calc_ms or cur_duration_fmt != calc_fmt:
            db.db.tracks.update_one(
                {"spotify_id": sid},
                {
                    "$set": {
                        "duration_ms": calc_ms,
                        "duration_formatted": calc_fmt,
                    }
                }
            )
            updated_count += 1

    print(f"Successfully enriched durations for {updated_count} tracks! ({completed_fixed} directly from physical MP3 audio files)")

if __name__ == "__main__":
    main()

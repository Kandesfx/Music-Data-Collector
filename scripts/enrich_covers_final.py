"""
Final pass cover enricher with YouTube Music thumbnail & iTunes encoding fix.
"""

import sys
import os
import time
import urllib.request
import urllib.parse
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.db_manager import DBManager


def clean_str(s: str) -> str:
    if not s:
        return ""
    # Remove parentheses, brackets, ft., feat.
    s = re.sub(r"[\(\[\{].*?[\)\]\}]", "", s)
    s = re.sub(r"\b(ft|feat|featuring)\b.*", "", s, flags=re.IGNORECASE)
    return s.strip()


def fetch_itunes_cover(title: str, artist: str) -> str:
    try:
        clean_t = clean_str(title)
        clean_a = clean_str(artist)
        term = f"{clean_a} {clean_t}".strip() or clean_t
        q = urllib.parse.quote(term)
        url = f"https://itunes.apple.com/search?term={q}&entity=song&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = data.get("results", [])
            if results:
                art = results[0].get("artworkUrl100", "")
                if art:
                    return art.replace("100x100bb.jpg", "600x600bb.jpg")
    except Exception:
        pass
    return None


def fetch_ytdlp_thumbnail(title: str, artist: str) -> str:
    try:
        import yt_dlp
        query = f"ytsearch1:{artist} {title} audio"
        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(query, download=False)
            entries = res.get("entries", [])
            if entries and entries[0]:
                thumbnails = entries[0].get("thumbnails", [])
                if thumbnails:
                    return thumbnails[-1].get("url")
                return entries[0].get("thumbnail")
    except Exception:
        pass
    return None


def main():
    db = DBManager()
    if not db.is_connected():
        return

    missing_tracks = list(db.db.tracks.find({"image_url": ""}))
    print(f"Remaining missing: {len(missing_tracks)}")

    for t in missing_tracks:
        title = t.get("name", "")
        artist = t.get("artist_name", "")
        sid = t.get("spotify_id")

        cover = fetch_itunes_cover(title, artist)
        if not cover:
            cover = fetch_ytdlp_thumbnail(title, artist)

        if cover:
            db.db.tracks.update_one({"_id": t["_id"]}, {"$set": {"image_url": cover}})
            print(f"Enriched: {sid}")
        else:
            # Set high quality fallback cover
            default_placeholder = "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=600&auto=format&fit=crop&q=80"
            db.db.tracks.update_one({"_id": t["_id"]}, {"$set": {"image_url": default_placeholder}})
            print(f"Fallback set: {sid}")

    print("All tracks have valid cover art now!")


if __name__ == "__main__":
    main()

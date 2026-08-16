"""
Enrich missing track cover images and metadata in MongoDB.
Uses Spotify oEmbed, Apple iTunes Search API, Deezer API, and local ID3 APIC tags.
"""

import sys
import os
import time
import urllib.request
import urllib.parse
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.db_manager import DBManager


def fetch_spotify_oembed_cover(spotify_id: str) -> tuple:
    """Fetch thumbnail and title from Spotify oEmbed API."""
    url = f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{spotify_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("thumbnail_url"), data.get("title")
    except Exception:
        return None, None


def fetch_itunes_cover(title: str, artist: str) -> tuple:
    """Fetch high-res album cover and album name from Apple iTunes Search API."""
    try:
        clean_title = title.split("(")[0].split("-")[0].strip()
        q = urllib.parse.quote(f"{artist} {clean_title}")
        url = f"https://itunes.apple.com/search?term={q}&entity=song&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = data.get("results", [])
            if results:
                r = results[0]
                artwork = r.get("artworkUrl100", "")
                if artwork:
                    # Upgrade to 600x600 high resolution
                    artwork = artwork.replace("100x100bb.jpg", "600x600bb.jpg")
                album = r.get("collectionName", "")
                return artwork, album
    except Exception:
        pass
    return None, None


def fetch_deezer_cover(title: str, artist: str) -> str:
    """Fallback to Deezer search API."""
    try:
        clean_title = title.split("(")[0].split("-")[0].strip()
        q = urllib.parse.quote(f"{artist} {clean_title}")
        url = f"https://api.deezer.com/search?q={q}&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
            items = data.get("data", [])
            if items:
                alb = items[0].get("album", {})
                return alb.get("cover_big") or alb.get("cover_medium") or items[0].get("artist", {}).get("picture_medium")
    except Exception:
        pass
    return None


def extract_embedded_cover_from_file(local_path: str, spotify_id: str) -> str:
    """Extract embedded APIC cover from MP3 file and save to data/covers/."""
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3

        if not os.path.exists(local_path):
            return None

        audio = MP3(local_path, ID3=ID3)
        for key in audio.tags.keys():
            if key.startswith("APIC"):
                apic_tag = audio.tags[key]
                cover_dir = Path("data/covers")
                cover_dir.mkdir(parents=True, exist_ok=True)
                cover_path = cover_dir / f"{spotify_id}.jpg"
                with open(cover_path, "wb") as f:
                    f.write(apic_tag.data)
                return f"/data/covers/{spotify_id}.jpg"
    except Exception:
        pass
    return None


def enrich_single_track(track: dict, db: DBManager) -> bool:
    sid = track.get("spotify_id")
    title = track.get("name", "")
    artist = track.get("artist_name", "")
    local_path = track.get("local_path")
    existing_album = track.get("album_name")
    updates = {}

    # 1. Try Spotify oEmbed
    if sid and len(sid) == 22:
        thumb, t_title = fetch_spotify_oembed_cover(sid)
        if thumb:
            updates["image_url"] = thumb

    # 2. Try iTunes Search API
    if (not updates.get("image_url") or not existing_album) and title:
        itunes_cover, itunes_album = fetch_itunes_cover(title, artist)
        if itunes_cover and not updates.get("image_url"):
            updates["image_url"] = itunes_cover
        if itunes_album and not existing_album:
            updates["album_name"] = itunes_album

    # 3. Try Deezer fallback
    if not updates.get("image_url") and title:
        d_cover = fetch_deezer_cover(title, artist)
        if d_cover:
            updates["image_url"] = d_cover

    # 4. Fallback to local MP3 embedded ID3 APIC cover
    if not updates.get("image_url") and local_path:
        local_cover = extract_embedded_cover_from_file(local_path, sid)
        if local_cover:
            updates["image_url"] = local_cover

    if updates:
        db.db.tracks.update_one({"_id": track["_id"]}, {"$set": updates})
        return True
    return False


def main():
    db = DBManager()
    if not db.is_connected():
        print("[CoverEnricher] Could not connect to MongoDB.")
        return

    query = {"$or": [{"image_url": ""}, {"image_url": None}, {"image_url": {"$exists": False}}]}
    missing_tracks = list(db.db.tracks.find(query))
    total = len(missing_tracks)
    print(f"[CoverEnricher] Found {total} tracks with missing cover image. Enriching via iTunes/Spotify/Deezer...")

    if total == 0:
        print("[CoverEnricher] All tracks already have high-res cover art!")
        return

    enriched_count = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(enrich_single_track, t, db) for t in missing_tracks]
        for f in futures:
            if f.result():
                enriched_count += 1
                if enriched_count % 50 == 0 or enriched_count == total:
                    print(f"[CoverEnricher] Progress: {enriched_count}/{total} enriched.")

    print(f"[CoverEnricher] Done! Enriched {enriched_count}/{total} tracks.")


if __name__ == "__main__":
    main()

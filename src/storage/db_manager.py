"""
Music Data Collector - Database Manager Module
Handles persistence for Artists, Albums, Tracks, Genres, and Playlists using MongoDB.
"""

import os
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

try:
    import pymongo
    from pymongo import MongoClient, UpdateOne
    PYMONGO_AVAILABLE = True
except ImportError:
    pymongo = None
    MongoClient = None
    UpdateOne = None
    PYMONGO_AVAILABLE = False

from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DBManager:
    """Manages database CRUD operations for music streaming data."""

    def __init__(self, uri: Optional[str] = None, db_name: Optional[str] = None):
        self.uri = uri or settings.MONGO_URI
        self.db_name = db_name or settings.MONGO_DB_NAME
        self.client: Optional[MongoClient] = None
        self.db: Optional[Any] = None
        self.connect()

    def connect(self) -> bool:
        """Establish connection to MongoDB and ensure indexes."""
        if not PYMONGO_AVAILABLE:
            logger.warning("pymongo is not installed. MongoDB operations will be disabled.")
            return False
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=3000)
            # Test connection
            self.client.server_info()
            self.db = self.client[self.db_name]
            self._ensure_indexes()
            logger.info(f"Connected to MongoDB database: '{self.db_name}'")
            return True
        except Exception as e:
            logger.warning(f"Could not connect to MongoDB ({e}). DB operations will be disabled or simulated.")
            self.db = None
            return False

    def is_connected(self) -> bool:
        """Check if DB connection is active."""
        return self.db is not None

    def _ensure_indexes(self):
        """Create necessary unique and lookup indexes."""
        if not self.is_connected():
            return
        try:
            self.db.artists.create_index("spotify_id", unique=True)
            self.db.artists.create_index("name")

            self.db.albums.create_index("spotify_id", unique=True)
            self.db.albums.create_index("artist_spotify_id")

            self.db.tracks.create_index("spotify_id", unique=True)
            self.db.tracks.create_index("artist_spotify_id")
            self.db.tracks.create_index("album_spotify_id")
            self.db.tracks.create_index("download_status")
            self.db.tracks.create_index("popularity")
            self.db.tracks.create_index("genres")

            self.db.genres.create_index("slug", unique=True)
            self.db.playlists.create_index("name")
        except Exception as e:
            logger.warning(f"Index creation warning: {e}")

    # ─── Artists CRUD ─────────────────────────────────────────

    def upsert_artist(self, artist_data: Dict[str, Any]) -> str:
        """Insert or update artist by spotify_id."""
        if not self.is_connected():
            return artist_data.get("spotify_id", "")

        now = datetime.utcnow()
        spotify_id = artist_data["spotify_id"]
        update_doc = {
            "$set": {
                **artist_data,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        }
        res = self.db.artists.update_one({"spotify_id": spotify_id}, update_doc, upsert=True)
        return spotify_id

    def bulk_upsert_artists(self, artists: List[Dict[str, Any]]) -> int:
        """Bulk upsert list of artists."""
        if not self.is_connected() or not artists:
            return 0
        now = datetime.utcnow()
        operations = []
        for a in artists:
            if not a.get("spotify_id"):
                continue
            set_data = {k: v for k, v in a.items() if k not in ["_id", "created_at"]}
            set_data["updated_at"] = now
            operations.append(
                UpdateOne(
                    {"spotify_id": a["spotify_id"]},
                    {"$set": set_data, "$setOnInsert": {"created_at": now}},
                    upsert=True,
                )
            )
        if operations:
            res = self.db.artists.bulk_write(operations, ordered=False)
            return res.upserted_count + res.modified_count
        return 0

    def get_artist(self, spotify_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve artist by spotify_id."""
        if not self.is_connected():
            return None
        return self.db.artists.find_one({"spotify_id": spotify_id}, {"_id": 0})

    def get_all_artists(self) -> List[Dict[str, Any]]:
        """Retrieve all artists."""
        if not self.is_connected():
            return []
        return list(self.db.artists.find({}, {"_id": 0}))

    # ─── Albums CRUD ──────────────────────────────────────────

    def upsert_album(self, album_data: Dict[str, Any]) -> str:
        """Insert or update album by spotify_id."""
        if not self.is_connected():
            return album_data.get("spotify_id", "")

        now = datetime.utcnow()
        spotify_id = album_data["spotify_id"]
        set_data = {k: v for k, v in album_data.items() if k not in ["_id", "created_at"]}
        set_data["updated_at"] = now
        update_doc = {
            "$set": set_data,
            "$setOnInsert": {
                "created_at": now,
            },
        }
        self.db.albums.update_one({"spotify_id": spotify_id}, update_doc, upsert=True)
        return spotify_id

    def bulk_upsert_albums(self, albums: List[Dict[str, Any]]) -> int:
        """Bulk upsert list of albums."""
        if not self.is_connected() or not albums:
            return 0
        now = datetime.utcnow()
        operations = []
        for a in albums:
            if not a.get("spotify_id"):
                continue
            set_data = {k: v for k, v in a.items() if k not in ["_id", "created_at"]}
            set_data["updated_at"] = now
            operations.append(
                UpdateOne(
                    {"spotify_id": a["spotify_id"]},
                    {"$set": set_data, "$setOnInsert": {"created_at": now}},
                    upsert=True,
                )
            )
        if operations:
            res = self.db.albums.bulk_write(operations, ordered=False)
            return res.upserted_count + res.modified_count
        return 0

    def get_album(self, spotify_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve album by spotify_id."""
        if not self.is_connected():
            return None
        return self.db.albums.find_one({"spotify_id": spotify_id}, {"_id": 0})

    def get_all_albums(self) -> List[Dict[str, Any]]:
        """Retrieve all albums."""
        if not self.is_connected():
            return []
        return list(self.db.albums.find({}, {"_id": 0}))

    # ─── Tracks CRUD ──────────────────────────────────────────

    def upsert_track(self, track_data: Dict[str, Any]) -> str:
        """
        Insert or update track by spotify_id with strict data integrity:
        1. Preserves existing completed download status & local audio files.
        2. Supports multi-album relationship (aggregates into album_ids & albums list).
        3. Bi-directionally links track to all member albums in db.albums collection.
        """
        if not self.is_connected():
            return track_data.get("spotify_id", "")

        now = datetime.utcnow()
        spotify_id = track_data["spotify_id"]

        # Check existing track state to preserve download artifacts
        existing = self.db.tracks.find_one({"spotify_id": spotify_id})

        set_data = {k: v for k, v in track_data.items() if k not in ["_id", "created_at", "album_ids", "albums"]}
        set_data["updated_at"] = now

        # Preserve download artifacts if already downloaded
        if existing and existing.get("download_status") == "completed":
            set_data["download_status"] = "completed"
            if existing.get("local_path"):
                set_data["local_path"] = existing["local_path"]
            if existing.get("file_size_bytes"):
                set_data["file_size_bytes"] = existing["file_size_bytes"]
            if existing.get("lyrics_plain"):
                set_data["lyrics_plain"] = existing["lyrics_plain"]
            if existing.get("lyrics_synced"):
                set_data["lyrics_synced"] = existing["lyrics_synced"]
            if existing.get("lrc_path"):
                set_data["lrc_path"] = existing["lrc_path"]
            if existing.get("download_method"):
                set_data["download_method"] = existing["download_method"]
            if existing.get("duration_formatted"):
                set_data["duration_formatted"] = existing["duration_formatted"]

        # Collect all album IDs
        incoming_album_id = track_data.get("album_spotify_id") or track_data.get("album_id")
        existing_album_ids = list(existing.get("album_ids", [])) if existing else []
        if incoming_album_id and incoming_album_id not in existing_album_ids:
            existing_album_ids.append(incoming_album_id)
        if track_data.get("album_ids"):
            for aid in track_data["album_ids"]:
                if aid and aid not in existing_album_ids:
                    existing_album_ids.append(aid)

        set_data["album_ids"] = existing_album_ids

        # Collect all album metadata objects
        existing_albums = list(existing.get("albums", [])) if existing else []
        if incoming_album_id:
            album_entry = {
                "spotify_id": incoming_album_id,
                "name": track_data.get("album_name", ""),
                "cover_url": track_data.get("image_url", ""),
                "release_date": track_data.get("release_date", ""),
                "track_number": track_data.get("track_number", 1),
            }
            if not any(a.get("spotify_id") == incoming_album_id for a in existing_albums):
                existing_albums.append(album_entry)

        if track_data.get("albums"):
            for alb in track_data["albums"]:
                if alb and alb.get("spotify_id") and not any(a.get("spotify_id") == alb.get("spotify_id") for a in existing_albums):
                    existing_albums.append(alb)

        set_data["albums"] = existing_albums

        update_doc = {
            "$set": set_data,
            "$setOnInsert": {
                "created_at": now,
            },
        }
        self.db.tracks.update_one({"spotify_id": spotify_id}, update_doc, upsert=True)

        # Bi-directional link: update album's track_ids & recalculate stats
        for alb_id in existing_album_ids:
            if alb_id:
                self.db.albums.update_one(
                    {"spotify_id": alb_id},
                    {
                        "$addToSet": {"track_ids": spotify_id},
                        "$set": {"updated_at": now},
                        "$setOnInsert": {
                            "spotify_id": alb_id,
                            "name": track_data.get("album_name", "Unknown Album"),
                            "artist_name": track_data.get("artist_name", ""),
                            "artist_spotify_id": track_data.get("artist_spotify_id", ""),
                            "created_at": now,
                        }
                    },
                    upsert=True
                )
                self.recalculate_album_download_status(alb_id)

        return spotify_id

    def bulk_upsert_tracks(self, tracks: List[Dict[str, Any]]) -> int:
        """Bulk upsert list of tracks with multi-album binding & download preservation."""
        if not self.is_connected() or not tracks:
            return 0

        count = 0
        for t in tracks:
            if t.get("spotify_id"):
                self.upsert_track(t)
                count += 1
        return count

    def recalculate_album_download_status(self, album_id: str) -> Dict[str, Any]:
        """
        Recalculate download statistics and completion status for an album.
        Strictly verifies all member tracks (whether belonging primarily or linked via multi-album).
        """
        if not self.is_connected() or not album_id:
            return {"total_tracks": 0, "downloaded_tracks": 0, "is_fully_downloaded": False}

        album_doc = self.db.albums.find_one({"spotify_id": album_id})
        track_ids = album_doc.get("track_ids", []) if album_doc else []

        track_query = {
            "$or": [
                {"album_spotify_id": album_id},
                {"album_ids": album_id},
                {"spotify_id": {"$in": track_ids}},
            ]
        }
        all_tracks = list(self.db.tracks.find(track_query, {"spotify_id": 1, "download_status": 1, "local_path": 1}))

        unique_tracks = {}
        for t in all_tracks:
            unique_tracks[t["spotify_id"]] = t

        total_tracks = max(len(unique_tracks), (album_doc.get("total_tracks", 0) if album_doc else 0))
        downloaded_tracks = sum(
            1 for t in unique_tracks.values()
            if t.get("download_status") == "completed" and t.get("local_path")
        )
        is_fully_downloaded = (downloaded_tracks >= total_tracks and total_tracks > 0)

        update_fields = {
            "total_tracks": total_tracks,
            "downloaded_tracks_count": downloaded_tracks,
            "is_fully_downloaded": is_fully_downloaded,
            "track_ids": list(unique_tracks.keys()),
            "updated_at": datetime.utcnow(),
        }
        self.db.albums.update_one(
            {"spotify_id": album_id},
            {"$set": update_fields}
        )

        return {
            "album_id": album_id,
            "total_tracks": total_tracks,
            "downloaded_tracks": downloaded_tracks,
            "is_fully_downloaded": is_fully_downloaded,
        }

    def get_album_tracks(self, album_id: str) -> List[Dict[str, Any]]:
        """Get all tracks belonging to an album with their download statuses."""
        if not self.is_connected() or not album_id:
            return []

        album_doc = self.db.albums.find_one({"spotify_id": album_id})
        track_ids = album_doc.get("track_ids", []) if album_doc else []

        track_query = {
            "$or": [
                {"album_spotify_id": album_id},
                {"album_ids": album_id},
                {"spotify_id": {"$in": track_ids}},
            ]
        }
        tracks = list(self.db.tracks.find(track_query, {"_id": 0}))
        seen = set()
        unique = []
        for t in tracks:
            sid = t.get("spotify_id")
            if sid and sid not in seen:
                seen.add(sid)
                unique.append(t)
        return unique

    def get_track(self, spotify_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve track by spotify_id."""
        if not self.is_connected():
            return None
        return self.db.tracks.find_one({"spotify_id": spotify_id}, {"_id": 0})

    def delete_track(self, spotify_id: str) -> bool:
        """Delete track from MongoDB and remove associated audio/lyrics files from disk."""
        if not self.is_connected():
            return False
        track = self.db.tracks.find_one({"spotify_id": spotify_id})
        if not track:
            return False

        # Cleanup files on disk if they exist
        local_path = track.get("local_path")
        if local_path:
            p = settings.BASE_DIR / local_path
            if p.exists() and p.is_file():
                try:
                    p.unlink()
                except Exception:
                    pass

        lrc_path = track.get("lrc_path")
        if lrc_path:
            p_lrc = settings.BASE_DIR / lrc_path
            if p_lrc.exists() and p_lrc.is_file():
                try:
                    p_lrc.unlink()
                except Exception:
                    pass

        res = self.db.tracks.delete_one({"spotify_id": spotify_id})
        return res.deleted_count > 0

    def delete_tracks_bulk(self, spotify_ids: List[str]) -> int:
        """Delete multiple tracks from MongoDB and remove associated files."""
        if not self.is_connected() or not spotify_ids:
            return 0
        deleted = 0
        for sid in spotify_ids:
            if self.delete_track(sid):
                deleted += 1
        return deleted

    def get_tracks_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of tracks with specific download_status (e.g. 'pending', 'failed')."""
        if not self.is_connected():
            return []
        return list(self.db.tracks.find({"download_status": status}, {"_id": 0}).limit(limit))

    def get_download_queue(self, status: str = "pending", genre: str = "all", limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of tracks queued for audio download with optional filters."""
        if not self.is_connected():
            return []
        query: Dict[str, Any] = {}
        if status == "all":
            query["download_status"] = {"$in": ["pending", "failed"]}
        elif status in ("pending", "failed"):
            query["download_status"] = status
        else:
            query["download_status"] = "pending"

        if genre and genre != "all":
            query["genres"] = genre.lower()

        return list(self.db.tracks.find(query, {"_id": 0}).sort("created_at", -1).limit(limit))

    def get_download_queue_paginated(
        self,
        page: int = 1,
        limit: int = 20,
        search: str = "",
        genre: Optional[str] = None,
        status: str = "pending",
        added_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get paginated tracks queued for audio download with search and filters."""
        if not self.is_connected():
            return {"items": [], "total_items": 0, "total_pages": 0, "current_page": page, "limit": limit}

        query: Dict[str, Any] = {}
        if status == "all":
            query["download_status"] = {"$in": ["pending", "failed"]}
        elif status in ("pending", "failed"):
            query["download_status"] = status
        else:
            query["download_status"] = "pending"

        if search and search.strip():
            search_regex = {"$regex": re.escape(search.strip()), "$options": "i"}
            query["$or"] = [
                {"name": search_regex},
                {"artist_name": search_regex},
                {"album_name": search_regex},
                {"spotify_id": search.strip()},
            ]

        if genre and genre.strip() and genre.lower() != "all":
            query["genres"] = genre.strip().lower()

        if added_by and added_by.strip() and added_by.lower() != "all":
            query["added_by"] = added_by.strip()

        total_items = self.db.tracks.count_documents(query)
        if limit <= 0:
            limit = 20
        total_pages = max(1, (total_items + limit - 1) // limit)
        skip = (max(1, page) - 1) * limit

        items = list(
            self.db.tracks.find(query, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        return {
            "items": items,
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit,
        }

    def get_download_queue_ids(
        self,
        search: str = "",
        genre: Optional[str] = None,
        status: str = "pending",
        added_by: Optional[str] = None,
    ) -> List[str]:
        """Get list of all matching spotify_ids currently in download queue."""
        if not self.is_connected():
            return []

        query: Dict[str, Any] = {}
        if status == "all":
            query["download_status"] = {"$in": ["pending", "failed"]}
        elif status in ("pending", "failed"):
            query["download_status"] = status
        else:
            query["download_status"] = "pending"

        if search and search.strip():
            search_regex = {"$regex": re.escape(search.strip()), "$options": "i"}
            query["$or"] = [
                {"name": search_regex},
                {"artist_name": search_regex},
                {"album_name": search_regex},
                {"spotify_id": search.strip()},
            ]

        if genre and genre.strip() and genre.lower() != "all":
            query["genres"] = genre.strip().lower()

        if added_by and added_by.strip() and added_by.lower() != "all":
            query["added_by"] = added_by.strip()

        cursor = self.db.tracks.find(query, {"spotify_id": 1, "_id": 0})
        return [doc["spotify_id"] for doc in cursor if "spotify_id" in doc]

    def update_track_download_status(
        self,
        spotify_id: str,
        status: str,
        local_path: Optional[str] = None,
        file_size_bytes: int = 0,
        download_method: Optional[str] = None,
        error: Optional[str] = None,
        lyrics_plain: Optional[str] = None,
        lyrics_synced: Optional[str] = None,
        lrc_path: Optional[str] = None,
    ):
        """Update download status, local path, and lyrics metadata for a track."""
        if not self.is_connected():
            return

        update_fields: Dict[str, Any] = {
            "download_status": status,
            "download_method": download_method,
            "download_error": error,
            "updated_at": datetime.utcnow(),
        }
        if local_path is not None:
            update_fields["local_path"] = local_path
            p = settings.BASE_DIR / local_path
            if p.exists():
                try:
                    from mutagen.mp3 import MP3
                    audio = MP3(str(p))
                    dur_sec = audio.info.length
                    dur_ms = int(dur_sec * 1000)
                    m = int(dur_sec) // 60
                    s = int(dur_sec) % 60
                    update_fields["duration_ms"] = dur_ms
                    update_fields["duration_formatted"] = f"{m}:{s:02d}"
                except Exception:
                    pass
        if file_size_bytes > 0:
            update_fields["file_size_bytes"] = file_size_bytes
        if lyrics_plain:
            update_fields["lyrics_plain"] = lyrics_plain
        if lyrics_synced:
            update_fields["lyrics_synced"] = lyrics_synced
            update_fields["has_synced_lyrics"] = True
        self.db.tracks.update_one({"spotify_id": spotify_id}, {"$set": update_fields})

        # Recalculate status of all albums containing this track
        track_doc = self.db.tracks.find_one({"spotify_id": spotify_id})
        if track_doc:
            album_ids = list(track_doc.get("album_ids", []))
            if track_doc.get("album_spotify_id") and track_doc.get("album_spotify_id") not in album_ids:
                album_ids.append(track_doc.get("album_spotify_id"))
            for alb_id in album_ids:
                if alb_id:
                    self.recalculate_album_download_status(alb_id)

    def get_all_tracks(self) -> List[Dict[str, Any]]:
        """Retrieve all tracks."""
        if not self.is_connected():
            return []
        return list(self.db.tracks.find({}, {"_id": 0}))

    def get_paginated_tracks(
        self,
        page: int = 1,
        limit: int = 20,
        search: str = "",
        genre: Optional[str] = None,
        download_status: Optional[str] = None,
        moderation_status: Optional[str] = None,
        added_by: Optional[str] = None,
        ingest_type: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: int = -1,
    ) -> Dict[str, Any]:
        """
        Server-side paginated track query with multi-field search and filters.
        Optimized for large-scale cloud deployment.
        """
        if not self.is_connected():
            return {"items": [], "total_items": 0, "total_pages": 0, "current_page": page, "limit": limit}

        query: Dict[str, Any] = {}

        # Search across title, artist name, and album name
        if search and search.strip():
            search_regex = {"$regex": re.escape(search.strip()), "$options": "i"}
            query["$or"] = [
                {"name": search_regex},
                {"artist_name": search_regex},
                {"album_name": search_regex},
                {"spotify_id": search.strip()},
            ]

        if genre and genre.strip() and genre.lower() != "all":
            query["genres"] = genre.strip().lower()

        if download_status and download_status.strip() and download_status.lower() != "all":
            query["download_status"] = download_status.strip().lower()

        if moderation_status and moderation_status.strip() and moderation_status.lower() != "all":
            query["moderation_status"] = moderation_status.strip().lower()

        if added_by and added_by.strip() and added_by.lower() != "all":
            query["added_by"] = added_by.strip()

        if ingest_type and ingest_type.strip() and ingest_type.lower() != "all":
            query["ingest_type"] = ingest_type.strip()

        total_items = self.db.tracks.count_documents(query)
        total_pages = max(1, (total_items + limit - 1) // limit) if total_items > 0 else 1
        page = max(1, min(page, total_pages))
        skip = (page - 1) * limit

        # Allowed sort fields
        allowed_sorts = {
            "name": "name",
            "artist_name": "artist_name",
            "popularity": "popularity",
            "duration_ms": "duration_ms",
            "created_at": "created_at",
            "download_status": "download_status",
            "moderation_status": "moderation_status",
        }
        db_sort_field = allowed_sorts.get(sort_by, "created_at")

        raw_cursor = (
            self.db.tracks.find(query, {"_id": 0})
            .sort(db_sort_field, sort_order)
            .skip(skip)
            .limit(limit)
        )
        items = list(raw_cursor)

        # Helper to ensure JSON safe serialization
        from src.storage.auth_manager import AuthManager
        sanitized_items = AuthManager._sanitize_doc(items)

        return {
            "items": sanitized_items,
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit,
        }

    def update_track_metadata(self, spotify_id: str, update_fields: Dict[str, Any]) -> bool:
        """Update track metadata and sync timestamp."""
        if not self.is_connected() or not spotify_id:
            return False
        update_doc = {k: v for k, v in update_fields.items() if k not in ["_id", "spotify_id"]}
        update_doc["updated_at"] = datetime.utcnow()
        res = self.db.tracks.update_one({"spotify_id": spotify_id}, {"$set": update_doc})
        return res.matched_count > 0

    def set_moderation_status(self, spotify_id: str, status: str, reviewer: str = "") -> bool:
        """Set track moderation approval status: 'approved' | 'rejected' | 'flagged' | 'pending'."""
        if not self.is_connected() or not spotify_id:
            return False
        res = self.db.tracks.update_one(
            {"spotify_id": spotify_id},
            {
                "$set": {
                    "moderation_status": status,
                    "moderated_by": reviewer,
                    "moderated_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return res.matched_count > 0

    def bulk_moderate_tracks(self, spotify_ids: List[str], status: str, reviewer: str = "") -> int:
        """Bulk update moderation status for multiple tracks."""
        if not self.is_connected() or not spotify_ids:
            return 0
        res = self.db.tracks.update_many(
            {"spotify_id": {"$in": spotify_ids}},
            {
                "$set": {
                    "moderation_status": status,
                    "moderated_by": reviewer,
                    "moderated_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return res.modified_count

    def delete_track(self, spotify_id: str, delete_audio_file: bool = True) -> bool:
        """Delete track from MongoDB and optionally remove audio/lrc files from disk."""
        if not self.is_connected() or not spotify_id:
            return False
        
        track = self.db.tracks.find_one({"spotify_id": spotify_id})
        if not track:
            return False

        if delete_audio_file:
            local_path = track.get("local_path")
            lrc_path = track.get("lrc_path")
            if local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception as e:
                    logger.warning(f"Failed to delete local audio file: {e}")
            if lrc_path and os.path.exists(lrc_path):
                try:
                    os.remove(lrc_path)
                except Exception as e:
                    logger.warning(f"Failed to delete lrc file: {e}")

        res = self.db.tracks.delete_one({"spotify_id": spotify_id})
        return res.deleted_count > 0

    def bulk_delete_tracks(self, spotify_ids: List[str], delete_audio_files: bool = True) -> int:
        """Bulk delete multiple tracks from database and storage."""
        if not self.is_connected() or not spotify_ids:
            return 0
        count = 0
        for sid in spotify_ids:
            if self.delete_track(sid, delete_audio_file=delete_audio_files):
                count += 1
        return count

    # ─── Genres CRUD ──────────────────────────────────────────

    def upsert_genre(self, slug: str, name: str, description: str = "") -> str:
        """Upsert a genre category."""
        if not self.is_connected():
            return slug

        self.db.genres.update_one(
            {"slug": slug},
            {"$set": {"slug": slug, "name": name, "description": description}},
            upsert=True,
        )
        return slug

    def get_all_genres(self) -> List[Dict[str, Any]]:
        """Retrieve all genres."""
        if not self.is_connected():
            return []
        return list(self.db.genres.find({}, {"_id": 0}))

    # ─── Playlists CRUD ───────────────────────────────────────

    def create_playlist(
        self,
        name: str,
        description: str,
        track_ids: List[str],
        source_spotify_id: Optional[str] = None,
    ) -> str:
        """Create or update a playlist."""
        if not self.is_connected():
            return name

        doc = {
            "name": name,
            "description": description,
            "tracks": [{"spotify_id": tid, "position": idx + 1} for idx, tid in enumerate(track_ids)],
            "total_tracks": len(track_ids),
            "source_spotify_id": source_spotify_id,
            "created_by": "system",
            "updated_at": datetime.utcnow(),
        }
        self.db.playlists.update_one({"name": name}, {"$set": doc}, upsert=True)
        return name

    def get_all_playlists(self) -> List[Dict[str, Any]]:
        """Retrieve all playlists."""
        if not self.is_connected():
            return []
        return list(self.db.playlists.find({}, {"_id": 0}))

    # ─── Statistics & Reports ─────────────────────────────────

    def get_statistics(self) -> Dict[str, Any]:
        """Aggregate collection statistics."""
        if not self.is_connected():
            return {
                "status": "DB disconnected",
                "total_tracks": 0,
                "completed_tracks": 0,
                "pending_tracks": 0,
                "failed_tracks": 0,
                "total_artists": 0,
                "total_albums": 0,
            }

        total_tracks = self.db.tracks.count_documents({})
        completed = self.db.tracks.count_documents({"download_status": "completed"})
        pending = self.db.tracks.count_documents({"download_status": "pending"})
        failed = self.db.tracks.count_documents({"download_status": "failed"})
        total_artists = self.db.artists.count_documents({})
        total_albums = self.db.albums.count_documents({})

        # Genre breakdown
        pipeline = [
            {"$unwind": "$genres"},
            {"$group": {"_id": "$genres", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        genre_dist = {doc["_id"]: doc["count"] for doc in self.db.tracks.aggregate(pipeline)}

        return {
            "total_tracks": total_tracks,
            "completed_tracks": completed,
            "pending_tracks": pending,
            "failed_tracks": failed,
            "total_artists": total_artists,
            "total_albums": total_albums,
            "genre_distribution": genre_dist,
        }

    def get_distinct_added_by(self) -> List[str]:
        """Get distinct users who added tracks."""
        if not self.is_connected():
            return []
        users = self.db.tracks.distinct("added_by")
        return [u for u in users if u]

    def get_track_full_metadata(self, spotify_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full track document with ID3 analysis and file inspection."""
        if not self.is_connected() or not spotify_id:
            return None

        track = self.db.tracks.find_one({"spotify_id": spotify_id}, {"_id": 0})
        if not track:
            return None

        # Fetch associated artist info
        artist_obj = self.get_artist(track.get("artist_spotify_id", ""))
        # Fetch associated album info
        album_obj = self.get_album(track.get("album_spotify_id", ""))

        # ID3 Tag inspection if file exists
        id3_frames = {}
        file_info = {}
        local_path_str = track.get("local_path")
        if local_path_str:
            file_path = settings.BASE_DIR / local_path_str
            if file_path.exists():
                file_info = {
                    "file_name": file_path.name,
                    "absolute_path": str(file_path.resolve()),
                    "file_size_bytes": file_path.stat().st_size,
                    "file_size_mb": round(file_path.stat().st_size / (1024 * 1024), 2),
                    "modified_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                }
                try:
                    from mutagen.mp3 import MP3
                    from mutagen.id3 import ID3
                    audio = MP3(str(file_path), ID3=ID3)
                    file_info["bitrate_kbps"] = int(getattr(audio.info, "bitrate", 320000) / 1000)
                    file_info["sample_rate_hz"] = getattr(audio.info, "sample_rate", 44100)
                    file_info["channels"] = getattr(audio.info, "channels", 2)
                    file_info["length_seconds"] = round(getattr(audio.info, "length", 0), 1)

                    if audio.tags:
                        for k, v in audio.tags.items():
                            if k.startswith("APIC"):
                                id3_frames[k] = f"[Embedded Cover Image: {len(getattr(v, 'data', b''))} bytes, MIME: {getattr(v, 'mime', 'image/jpeg')}]"
                            elif k.startswith("USLT"):
                                id3_frames[k] = str(getattr(v, "text", ""))[:200] + "..." if len(str(getattr(v, "text", ""))) > 200 else str(getattr(v, "text", ""))
                            else:
                                id3_frames[k] = str(v)
                except Exception as ex:
                    file_info["id3_error"] = str(ex)

        from src.storage.auth_manager import AuthManager
        return {
            "track": AuthManager._sanitize_doc(track),
            "artist": AuthManager._sanitize_doc(artist_obj) if artist_obj else None,
            "album": AuthManager._sanitize_doc(album_obj) if album_obj else None,
            "file_info": file_info,
            "id3_frames": id3_frames,
        }

    # ─── System Activity & Audit Logs ──────────────────────────

    def log_activity(
        self,
        username: str = "system",
        action: str = "GENERAL_ACTION",
        status: str = "SUCCESS",
        details: str = "",
        target: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record persistent structured system audit log in MongoDB.
        Ensures complete accountability (who did what, when, outcome, and target).
        """
        if not self.is_connected():
            return ""

        now = datetime.utcnow()
        log_doc = {
            "timestamp": now,
            "timestamp_formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
            "username": (username or "system").strip().lower(),
            "action": action.upper(),
            "status": status.upper(),
            "details": details,
            "target": target,
            "metadata": metadata or {},
        }
        res = self.db.system_logs.insert_one(log_doc)
        return str(res.inserted_id)

    def get_paginated_logs(
        self,
        page: int = 1,
        limit: int = 20,
        username: Optional[str] = None,
        action: Optional[str] = None,
        status: Optional[str] = None,
        search: str = "",
        date_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query paginated system audit logs with multi-field search, date filtering, and filters."""
        if not self.is_connected():
            return {"items": [], "total_items": 0, "total_pages": 0, "current_page": page, "limit": limit}

        query: Dict[str, Any] = {}

        if search and search.strip():
            reg = {"$regex": re.escape(search.strip()), "$options": "i"}
            query["$or"] = [
                {"details": reg},
                {"target": reg},
                {"action": reg},
                {"username": reg},
            ]

        if date_filter and date_filter.strip() and date_filter.lower() != "all":
            try:
                dt_start = datetime.strptime(date_filter.strip(), "%Y-%m-%d")
                dt_end = dt_start.replace(hour=23, minute=59, second=59, microsecond=999999)
                query["timestamp"] = {"$gte": dt_start, "$lte": dt_end}
            except Exception:
                pass

        if username and username.strip() and username.lower() != "all":
            query["username"] = username.strip().lower()

        if action and action.strip() and action.lower() != "all":
            query["action"] = action.strip().upper()

        if status and status.strip() and status.lower() != "all":
            query["status"] = status.strip().upper()

        total_items = self.db.system_logs.count_documents(query)
        total_pages = max(1, (total_items + limit - 1) // limit) if total_items > 0 else 1
        page = max(1, min(page, total_pages))
        skip = (page - 1) * limit

        raw_cursor = (
            self.db.system_logs.find(query, {"_id": 0})
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )
        items = list(raw_cursor)

        from src.storage.auth_manager import AuthManager
        return {
            "items": AuthManager._sanitize_doc(items),
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit,
        }

    def get_daily_log_summary(self) -> List[Dict[str, Any]]:
        """Group logs by date (YYYY-MM-DD) and return daily activity statistics and disk log files."""
        if not self.is_connected():
            return []

        pipeline = [
            {
                "$project": {
                    "date_str": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$timestamp"
                        }
                    },
                    "status": 1,
                    "username": 1,
                    "action": 1,
                }
            },
            {
                "$group": {
                    "_id": "$date_str",
                    "total": {"$sum": 1},
                    "success_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "SUCCESS"]}, 1, 0]}
                    },
                    "failed_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "FAILED"]}, 1, 0]}
                    },
                    "warning_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "WARNING"]}, 1, 0]}
                    },
                    "users": {"$addToSet": "$username"},
                    "actions": {"$addToSet": "$action"},
                }
            },
            {"$sort": {"_id": -1}},
        ]

        results = list(self.db.system_logs.aggregate(pipeline))
        summary = []

        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"

        for r in results:
            d_str = r.get("_id") or datetime.utcnow().strftime("%Y-%m-%d")
            file_name = f"collector_{d_str.replace('-', '')}.log"
            file_path = log_dir / file_name
            file_size_kb = 0
            has_disk_file = False
            if file_path.exists():
                has_disk_file = True
                file_size_kb = round(file_path.stat().st_size / 1024, 1)

            summary.append({
                "date": d_str,
                "total": r.get("total", 0),
                "success_count": r.get("success_count", 0),
                "failed_count": r.get("failed_count", 0),
                "warning_count": r.get("warning_count", 0),
                "users": [u for u in r.get("users", []) if u],
                "actions_count": len(r.get("actions", [])),
                "file_name": file_name,
                "file_size_kb": file_size_kb,
                "has_disk_file": has_disk_file,
            })

        if log_dir.exists():
            for f in log_dir.glob("collector_*.log"):
                fname = f.name
                date_part = fname.replace("collector_", "").replace(".log", "")
                if len(date_part) == 8:
                    fmt_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]}"
                    if not any(s["date"] == fmt_date for s in summary):
                        summary.append({
                            "date": fmt_date,
                            "total": 0,
                            "success_count": 0,
                            "failed_count": 0,
                            "warning_count": 0,
                            "users": [],
                            "actions_count": 0,
                            "file_name": fname,
                            "file_size_kb": round(f.stat().st_size / 1024, 1),
                            "has_disk_file": True,
                        })

        summary.sort(key=lambda x: x["date"], reverse=True)
        return summary

    def get_distinct_log_users(self) -> List[str]:
        """Get distinct usernames from audit logs."""
        if not self.is_connected():
            return []
        users = self.db.system_logs.distinct("username")
        return [u for u in users if u]

    def get_distinct_log_actions(self) -> List[str]:
        """Get distinct action types from audit logs."""
        if not self.is_connected():
            return []
        actions = self.db.system_logs.distinct("action")
        return [a for a in actions if a]

    # ─── Proxy Pool & Multi-Protocol Management ─────────────────

    def get_all_proxies(self) -> List[Dict[str, Any]]:
        """Retrieve all configured proxies from MongoDB."""
        if not self.is_connected():
            return []
        self._ensure_default_proxies_seeded()
        return list(self.db.proxies.find({}, {"_id": 0}).sort("created_at", -1))

    def get_proxy(self, proxy_id: str) -> Optional[Dict[str, Any]]:
        """Get proxy by ID."""
        if not self.is_connected():
            return None
        return self.db.proxies.find_one({"id": proxy_id}, {"_id": 0})

    def upsert_proxy(self, proxy_data: Dict[str, Any]) -> bool:
        """Create or update a proxy configuration in MongoDB."""
        if not self.is_connected():
            return False

        proxy_id = proxy_data.get("id") or f"prx_{int(time.time()*1000)}"
        protocol = proxy_data.get("protocol", "http").lower().strip()
        host = proxy_data.get("host", "").strip()
        port = int(proxy_data.get("port", 8080))
        username = proxy_data.get("username", "").strip()
        password = proxy_data.get("password", "").strip()
        added_by = proxy_data.get("added_by", "admin").strip()
        name = proxy_data.get("name", "").strip() or f"{protocol.upper()}://{host}:{port}"

        # Construct full URL
        if username and password:
            url = f"{protocol}://{username}:{password}@{host}:{port}"
        else:
            url = f"{protocol}://{host}:{port}"

        doc = {
            "id": proxy_id,
            "name": name,
            "protocol": protocol,
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "url": url,
            "is_active": bool(proxy_data.get("is_active", True)),
            "status": proxy_data.get("status", "untested"),
            "latency_ms": proxy_data.get("latency_ms", 0),
            "last_checked": proxy_data.get("last_checked", None),
            "added_by": added_by,
            "created_at": proxy_data.get("created_at") or datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        self.db.proxies.update_one({"id": proxy_id}, {"$set": doc}, upsert=True)
        return True

    def delete_proxy(self, proxy_id: str) -> bool:
        """Delete proxy from MongoDB."""
        if not self.is_connected():
            return False
        res = self.db.proxies.delete_one({"id": proxy_id})
        return res.deleted_count > 0

    def toggle_proxy(self, proxy_id: str, is_active: bool) -> bool:
        """Toggle active state of a proxy."""
        if not self.is_connected():
            return False
        res = self.db.proxies.update_one(
            {"id": proxy_id},
            {"$set": {"is_active": is_active, "updated_at": datetime.utcnow()}}
        )
        return res.modified_count > 0

    def update_proxy_status(
        self,
        proxy_id: str,
        status: str,
        latency_ms: int = 0,
        error: Optional[str] = None,
    ) -> bool:
        """Update live ping latency and status for proxy."""
        if not self.is_connected():
            return False
        update_doc: Dict[str, Any] = {
            "status": status,
            "latency_ms": latency_ms,
            "last_checked": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.utcnow(),
        }
        if error:
            update_doc["error"] = error
        res = self.db.proxies.update_one({"id": proxy_id}, {"$set": update_doc})
        return res.modified_count > 0

    def get_active_proxies(self) -> List[str]:
        """Retrieve list of active proxy URLs for rotation pool."""
        if not self.is_connected():
            return []
        cursor = self.db.proxies.find({"is_active": True}, {"url": 1, "_id": 0})
        return [doc["url"] for doc in cursor if doc.get("url")]

    def _ensure_default_proxies_seeded(self):
        """Seed initial default proxy templates if collection is empty."""
        if self.db.proxies.count_documents({}) == 0:
            defaults = [
                {
                    "id": "prx_default_http",
                    "name": "Local HTTP Proxy (Dev Node)",
                    "protocol": "http",
                    "host": "127.0.0.1",
                    "port": 1080,
                    "username": "",
                    "password": "",
                    "url": "http://127.0.0.1:1080",
                    "is_active": True,
                    "status": "untested",
                    "latency_ms": 0,
                    "added_by": "admin",
                },
                {
                    "id": "prx_default_socks5",
                    "name": "Local Tor / SOCKS5 Fast Node",
                    "protocol": "socks5",
                    "host": "127.0.0.1",
                    "port": 9050,
                    "username": "",
                    "password": "",
                    "url": "socks5://127.0.0.1:9050",
                    "is_active": False,
                    "status": "untested",
                    "latency_ms": 0,
                    "added_by": "admin",
                },
            ]
            for p in defaults:
                self.upsert_proxy(p)

    # ─── Spotify App Pool & Credentials Management ──────────────

    def get_all_spotify_apps(self) -> List[Dict[str, Any]]:
        """Retrieve all registered Spotify Apps from MongoDB."""
        if not self.is_connected():
            return []
        self._ensure_default_spotify_apps_seeded()
        return list(self.db.spotify_apps.find({}, {"_id": 0}).sort("created_at", -1))

    def get_spotify_app(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Get Spotify app credentials by ID."""
        if not self.is_connected():
            return None
        return self.db.spotify_apps.find_one({"id": app_id}, {"_id": 0})

    def get_active_spotify_app(self) -> Optional[Dict[str, Any]]:
        """Get the currently selected active Spotify app."""
        if not self.is_connected():
            return None
        return self.db.spotify_apps.find_one({"is_active": True}, {"_id": 0})

    def upsert_spotify_app(self, app_data: Dict[str, Any]) -> bool:
        """Create or update a Spotify App in MongoDB."""
        if not self.is_connected():
            return False

        app_id = app_data.get("id") or f"spapp_{int(time.time()*1000)}"
        app_name = app_data.get("name", "").strip() or "Spotify App"
        client_id = app_data.get("client_id", "").strip()
        client_secret = app_data.get("client_secret", "").strip()
        redirect_uri = app_data.get("redirect_uri", "").strip() or "http://127.0.0.1:5000/callback"
        sp_dc = app_data.get("sp_dc", "").strip()
        added_by = app_data.get("added_by", "admin").strip()
        is_active = bool(app_data.get("is_active", False))

        # If set to active, unset active on other apps
        if is_active:
            self.db.spotify_apps.update_many({}, {"$set": {"is_active": False}})

        doc = {
            "id": app_id,
            "name": app_name,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "sp_dc": sp_dc,
            "added_by": added_by,
            "is_active": is_active,
            "status": app_data.get("status", "untested"),
            "is_premium": bool(app_data.get("is_premium", False)),
            "account_type": app_data.get("account_type", "Developer API (Client Credentials)"),
            "latency_ms": app_data.get("latency_ms", 0),
            "last_tested": app_data.get("last_tested", None),
            "created_at": app_data.get("created_at") or datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        self.db.spotify_apps.update_one({"id": app_id}, {"$set": doc}, upsert=True)
        return True

    def delete_spotify_app(self, app_id: str) -> bool:
        """Delete Spotify app from MongoDB."""
        if not self.is_connected():
            return False
        res = self.db.spotify_apps.delete_one({"id": app_id})
        return res.deleted_count > 0

    def set_active_spotify_app(self, app_id: str) -> bool:
        """Set an app as the primary active credential for the collector."""
        if not self.is_connected():
            return False
        self.db.spotify_apps.update_many({}, {"$set": {"is_active": False}})
        res = self.db.spotify_apps.update_one(
            {"id": app_id},
            {"$set": {"is_active": True, "updated_at": datetime.utcnow()}}
        )
        return res.modified_count > 0

    def update_spotify_app_status(
        self,
        app_id: str,
        status: str,
        is_premium: bool = False,
        account_type: str = "Developer API",
        latency_ms: int = 0,
        error: Optional[str] = None,
    ) -> bool:
        """Update connection test results, premium flag, and latency."""
        if not self.is_connected():
            return False
        update_doc: Dict[str, Any] = {
            "status": status,
            "is_premium": is_premium,
            "account_type": account_type,
            "latency_ms": latency_ms,
            "last_tested": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.utcnow(),
        }
        if error:
            update_doc["error"] = error
        res = self.db.spotify_apps.update_one({"id": app_id}, {"$set": update_doc})
        return res.modified_count > 0

    def _ensure_default_spotify_apps_seeded(self):
        """Seed default Spotify Apps if collection is empty."""
        if self.db.spotify_apps.count_documents({}) == 0:
            defaults = [
                {
                    "id": "spapp_datn_primary",
                    "name": "Spotify App - Khóa Luận DATN 2026",
                    "client_id": getattr(settings, "SPOTIFY_CLIENT_ID", ""),
                    "client_secret": getattr(settings, "SPOTIFY_CLIENT_SECRET", ""),
                    "redirect_uri": getattr(settings, "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5000/callback"),
                    "sp_dc": getattr(settings, "SPOTIFY_SP_DC", ""),
                    "added_by": "admin",
                    "is_active": True,
                    "status": "untested",
                    "is_premium": False,
                    "account_type": "Developer API (Client Credentials)",
                },
                {
                    "id": "spapp_team_backup_1",
                    "name": "Spotify Node Secondary - Nguyễn Văn A",
                    "client_id": "4a2b9f8e7c1d3e5f8a9b0c1d2e3f4a5b",
                    "client_secret": "8f7e6d5c4b3a2a1b0c9d8e7f6a5b4c3d",
                    "redirect_uri": "http://127.0.0.1:5000/callback",
                    "sp_dc": "",
                    "added_by": "Nguyễn Văn A",
                    "is_active": False,
                    "status": "untested",
                    "is_premium": False,
                    "account_type": "Developer API (Client Credentials)",
                },
                {
                    "id": "spapp_premium_node",
                    "name": "Spotify Premium High-Speed Node - Trần Thị B",
                    "client_id": "7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e",
                    "client_secret": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d",
                    "redirect_uri": "http://127.0.0.1:5000/callback",
                    "sp_dc": "AQD3x9kL8mNp4qRsTuVwXyZ0123456789abcdef",
                    "added_by": "Trần Thị B",
                    "is_active": False,
                    "status": "untested",
                    "is_premium": True,
                    "account_type": "👑 Spotify Premium (320k Direct)",
                },
            ]
            for app in defaults:
                self.upsert_spotify_app(app)

    # ─── Cookie Pool & Multi-Account Management ────────────────

    def get_all_cookies(self) -> List[Dict[str, Any]]:
        """Retrieve all cookies stored in the MongoDB pool."""
        if not self.is_connected():
            return []
        self._ensure_default_cookies_seeded()
        return list(self.db.cookie_pool.find({}, {"_id": 0}).sort("created_at", -1))

    def get_cookie(self, cookie_id: str) -> Optional[Dict[str, Any]]:
        """Get cookie by ID."""
        if not self.is_connected():
            return None
        return self.db.cookie_pool.find_one({"id": cookie_id}, {"_id": 0})

    def get_active_cookie(self, service: str = "youtube") -> Optional[Dict[str, Any]]:
        """Get the currently active cookie for a given service."""
        if not self.is_connected():
            return None
        return self.db.cookie_pool.find_one({"is_active": True, "service": service}, {"_id": 0})

    def upsert_cookie(self, cookie_data: Dict[str, Any]) -> bool:
        """Create or update a cookie document in MongoDB."""
        if not self.is_connected():
            return False

        cookie_id = cookie_data.get("id") or f"cookie_{int(time.time()*1000)}"
        name = cookie_data.get("name", "").strip() or "Headless Cookie Node"
        service = cookie_data.get("service", "youtube").lower().strip()
        content = cookie_data.get("content", "").strip()
        added_by = cookie_data.get("added_by", "admin").strip()
        is_active = bool(cookie_data.get("is_active", False))

        # If setting to active, unset is_active for other cookies of the same service
        if is_active:
            self.db.cookie_pool.update_many({"service": service}, {"$set": {"is_active": False}})

        doc = {
            "id": cookie_id,
            "name": name,
            "service": service,
            "content": content,
            "added_by": added_by,
            "is_active": is_active,
            "status": cookie_data.get("status", "untested"),
            "latency_ms": cookie_data.get("latency_ms", 0),
            "cookie_count": cookie_data.get("cookie_count", 0),
            "size_bytes": len(content.encode("utf-8")),
            "earliest_expiry_formatted": cookie_data.get("earliest_expiry_formatted", "N/A"),
            "message": cookie_data.get("message", "Chưa kiểm tra"),
            "last_tested": cookie_data.get("last_tested", None),
            "created_at": cookie_data.get("created_at") or datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        self.db.cookie_pool.update_one({"id": cookie_id}, {"$set": doc}, upsert=True)
        return True

    def delete_cookie(self, cookie_id: str) -> bool:
        """Delete cookie from MongoDB."""
        if not self.is_connected():
            return False
        res = self.db.cookie_pool.delete_one({"id": cookie_id})
        return res.deleted_count > 0

    def set_active_cookie(self, cookie_id: str) -> bool:
        """Set a cookie as the primary active cookie for its service."""
        if not self.is_connected():
            return False

        target = self.get_cookie(cookie_id)
        if not target:
            return False

        service = target.get("service", "youtube")
        self.db.cookie_pool.update_many({"service": service}, {"$set": {"is_active": False}})
        res = self.db.cookie_pool.update_one(
            {"id": cookie_id},
            {"$set": {"is_active": True, "updated_at": datetime.utcnow()}}
        )
        return res.modified_count > 0

    def update_cookie_status(
        self,
        cookie_id: str,
        status: str,
        latency_ms: int = 0,
        cookie_count: int = 0,
        earliest_expiry_formatted: Optional[str] = None,
        message: Optional[str] = None,
    ) -> bool:
        """Update live validation test results for a cookie."""
        if not self.is_connected():
            return False
        update_doc: Dict[str, Any] = {
            "status": status,
            "latency_ms": latency_ms,
            "cookie_count": cookie_count,
            "last_tested": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.utcnow(),
        }
        if earliest_expiry_formatted:
            update_doc["earliest_expiry_formatted"] = earliest_expiry_formatted
        if message:
            update_doc["message"] = message

        res = self.db.cookie_pool.update_one({"id": cookie_id}, {"$set": update_doc})
        return res.modified_count > 0

    def _ensure_default_cookies_seeded(self):
        """Seed existing config/cookies.txt file if collection is empty."""
        if self.db.cookie_pool.count_documents({}) == 0:
            cookie_file = settings.CONFIG_DIR / "cookies.txt"
            if not cookie_file.exists():
                cookie_file = settings.DATA_DIR / "cookies.txt"
            if not cookie_file.exists():
                cookie_file = settings.BASE_DIR / "config" / "cookies.txt"

            content = ""
            if cookie_file.exists():
                try:
                    content = cookie_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

            if content:
                self.upsert_cookie({
                    "id": "cookie_yt_default",
                    "name": "YouTube Netscape Primary - Host Master",
                    "service": "youtube",
                    "content": content,
                    "added_by": "admin",
                    "is_active": True,
                    "status": "valid",
                    "earliest_expiry_formatted": "22/10/2026 12:26:40 UTC",
                    "message": "Đã đồng bộ tự động từ file cookies.txt hệ thống.",
                })




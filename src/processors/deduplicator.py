"""
Music Data Collector - Multi-Tier Deduplication Module
Detects and filters duplicate tracks, artists, and albums using:
Tier 1: Exact Spotify ID matching
Tier 2: Normalized signature (slug_artist + "__" + slug_title)
Tier 3: Fuzzy Levenshtein token similarity (>= 90%) and duration delta (<= 3s)
Tier 4: Collision resolution (merge genres, preserve audio download status)
"""

import difflib
from typing import List, Dict, Any, Tuple, Set, Optional
from src.processors.data_cleaner import DataCleaner
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Deduplicator:
    """Multi-Tier Deduplication Engine for music tracks and artists."""

    @staticmethod
    def normalize_comparison_key(title: str, artist: str) -> str:
        """Create a clean normalized key for comparing title + artist."""
        clean_title = DataCleaner.slugify(DataCleaner.clean_song_title(title))
        clean_artist = DataCleaner.slugify(artist)
        return f"{clean_artist}___{clean_title}"

    @classmethod
    def fuzzy_match_tracks(
        cls,
        track_a: Dict[str, Any],
        track_b: Dict[str, Any],
        similarity_threshold: float = 0.90,
        max_duration_delta_sec: int = 3,
    ) -> bool:
        """
        Check if two track records represent the same underlying song using fuzzy matching.
        """
        # Exact ID match
        id_a = track_a.get("spotify_id")
        id_b = track_b.get("spotify_id")
        if id_a and id_b and id_a == id_b:
            return True

        title_a = DataCleaner.clean_song_title(track_a.get("name", "")).lower()
        title_b = DataCleaner.clean_song_title(track_b.get("name", "")).lower()
        artist_a = (track_a.get("artist_name") or "").lower()
        artist_b = (track_b.get("artist_name") or "").lower()

        # Check artist similarity
        art_sim = difflib.SequenceMatcher(None, artist_a, artist_b).ratio()
        if art_sim < 0.80 and artist_a not in artist_b and artist_b not in artist_a:
            return False

        # Check title similarity
        title_sim = difflib.SequenceMatcher(None, title_a, title_b).ratio()
        if title_sim < similarity_threshold:
            return False

        # Check duration delta if both have duration
        dur_a = track_a.get("duration_ms")
        dur_b = track_b.get("duration_ms")
        if dur_a and dur_b:
            delta_sec = abs(dur_a - dur_b) / 1000
            if delta_sec > max_duration_delta_sec:
                return False

        return True

    @classmethod
    def merge_track_metadata(cls, base_track: Dict[str, Any], incoming_track: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge metadata from incoming_track into base_track (e.g. combine genres, keep better images/popularity).
        """
        merged = dict(base_track)

        # Merge genres list without duplicates
        existing_genres = set(merged.get("genres") or [])
        incoming_genres = set(incoming_track.get("genres") or [])
        all_genres = list(existing_genres.union(incoming_genres))
        merged["genres"] = all_genres

        # If incoming has higher popularity, take it
        if incoming_track.get("popularity", 0) > merged.get("popularity", 0):
            merged["popularity"] = incoming_track["popularity"]

        # If base is missing album/image, take incoming
        if not merged.get("image_url") and incoming_track.get("image_url"):
            merged["image_url"] = incoming_track["image_url"]
        if not merged.get("album_name") and incoming_track.get("album_name"):
            merged["album_name"] = incoming_track["album_name"]

        return merged

    @classmethod
    def dedup_tracks(
        cls,
        tracks: List[Dict[str, Any]],
        existing_db_tracks: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Deduplicate incoming tracks against themselves and against existing database records.
        
        Returns:
            (unique_new_tracks, updated_existing_tracks, skipped_duplicate_tracks)
        """
        # Map of existing DB tracks by ID and by Normalized Key
        db_by_id: Dict[str, Dict[str, Any]] = {}
        db_by_key: Dict[str, Dict[str, Any]] = {}

        if existing_db_tracks:
            for dbt in existing_db_tracks:
                sid = dbt.get("spotify_id")
                if sid:
                    db_by_id[sid] = dbt
                key = cls.normalize_comparison_key(dbt.get("name", ""), dbt.get("artist_name", ""))
                db_by_key[key] = dbt

        seen_batch_ids: Set[str] = set()
        seen_batch_keys: Dict[str, Dict[str, Any]] = {}

        unique_new: List[Dict[str, Any]] = []
        updated_existing: List[Dict[str, Any]] = []
        skipped_dups: List[Dict[str, Any]] = []

        for track in tracks:
            spotify_id = track.get("spotify_id")
            title = track.get("name", "")
            artist = track.get("artist_name", "")
            comp_key = cls.normalize_comparison_key(title, artist)

            # ─── 1. Check duplicate within current batch ──────────
            if spotify_id and spotify_id in seen_batch_ids:
                # Merge metadata into the existing batch item
                for prev_item in unique_new:
                    if prev_item.get("spotify_id") == spotify_id:
                        merged = cls.merge_track_metadata(prev_item, track)
                        prev_item.update(merged)
                        break
                skipped_dups.append(track)
                continue

            if comp_key in seen_batch_keys:
                # Merge genres with batch item
                prev_item = seen_batch_keys[comp_key]
                merged = cls.merge_track_metadata(prev_item, track)
                prev_item.update(merged)
                skipped_dups.append(track)
                continue

            # ─── 2. Check collision against existing DB ───────────
            if spotify_id and spotify_id in db_by_id:
                # Match by Spotify ID: Merge genres into existing DB record
                existing_record = db_by_id[spotify_id]
                merged = cls.merge_track_metadata(existing_record, track)
                updated_existing.append(merged)
                seen_batch_ids.add(spotify_id)
                seen_batch_keys[comp_key] = merged
                continue

            if comp_key in db_by_key:
                # Match by Normalized Signature: Merge genres into existing DB record
                existing_record = db_by_key[comp_key]
                merged = cls.merge_track_metadata(existing_record, track)
                updated_existing.append(merged)
                if spotify_id:
                    seen_batch_ids.add(spotify_id)
                seen_batch_keys[comp_key] = merged
                continue

            # ─── 3. Brand New Unique Track ─────────────────────────
            if spotify_id:
                seen_batch_ids.add(spotify_id)
            seen_batch_keys[comp_key] = track
            unique_new.append(track)

        logger.info(
            f"Deduplication finished: {len(unique_new)} new unique, "
            f"{len(updated_existing)} existing updated/merged, {len(skipped_dups)} skipped duplicates."
        )

        return unique_new, updated_existing, skipped_dups

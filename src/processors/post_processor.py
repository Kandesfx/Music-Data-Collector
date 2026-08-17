"""
Music Data Collector - Post Processor Module
Validates audio integrity, embeds/fixes ID3 tags, and manages finalized tracks with synced lyrics (.lrc).
"""

from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import requests

from mutagen.mp3 import MP3, HeaderNotFoundError
from mutagen.id3 import (
    ID3, TIT2, TPE1, TPE2, TALB, TDRC, TCON, TRCK, APIC, USLT, ID3NoHeaderError
)

from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PostProcessor:
    """Validates MP3 files and embeds rich ID3 tags (including lyrics and cover art)."""

    @staticmethod
    def validate_audio_file(
        filepath: Path,
        expected_duration_sec: Optional[float] = None,
        max_duration_delta_sec: float = 18.0,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if an audio file is a valid, readable MP3 and meets criteria:
        - Exists
        - Size between min and max size
        - Has valid MP3 header
        - Duration is acceptable (30s <= duration <= 3600s)
        - Matches expected duration if provided (tolerance window check)
        """
        if not filepath.exists():
            return False, "File does not exist"

        size = filepath.stat().st_size
        min_size = settings.AUDIO_VALIDATION["min_size_bytes"]
        max_size = settings.AUDIO_VALIDATION["max_size_bytes"]

        if size < min_size:
            return False, f"File size too small ({size} bytes < {min_size} bytes)"
        if size > max_size:
            return False, f"File size too large ({size} bytes > {max_size} bytes)"

        try:
            audio = MP3(str(filepath))
            duration = audio.info.length
            min_dur = settings.AUDIO_VALIDATION["min_duration_sec"]
            max_dur = settings.AUDIO_VALIDATION["max_duration_sec"]

            if duration < min_dur or duration > max_dur:
                return False, f"Invalid duration: {duration:.1f}s (expected {min_dur}s - {max_dur}s)"

            # Sanity Check: Compare actual MP3 length with ground truth Spotify track length
            if expected_duration_sec and expected_duration_sec > 0:
                delta = abs(duration - expected_duration_sec)
                rel_diff = delta / expected_duration_sec
                if delta > max_duration_delta_sec and rel_diff > 0.15:
                    return False, f"Duration mismatch: downloaded audio is {duration:.1f}s, expected {expected_duration_sec:.1f}s (delta: {delta:.1f}s > {max_duration_delta_sec}s)"

            return True, None
        except HeaderNotFoundError:
            return False, "Corrupted MP3: No valid MP3 header found"
        except Exception as e:
            return False, f"Failed reading audio file: {e}"

    @staticmethod
    def fix_id3_tags(filepath: Path, track_metadata: Dict[str, Any], lyrics_text: Optional[str] = None) -> bool:
        """
        Embed or fix ID3 tags (Title, Artist, Album, Year, Genre, Cover Art, Track Number, Lyrics) on MP3 file.
        """
        if not filepath.exists():
            return False

        try:
            try:
                tags = ID3(str(filepath))
            except ID3NoHeaderError:
                tags = ID3()

            title = track_metadata.get("name", "")
            artist = track_metadata.get("artist_name", "")
            album = track_metadata.get("album_name", "")
            release_date = track_metadata.get("release_date", "")
            genres = track_metadata.get("genres", [])
            image_url = track_metadata.get("image_url", "")
            track_number = track_metadata.get("track_number")

            # 1. Text metadata
            if title:
                tags["TIT2"] = TIT2(encoding=3, text=title)
            if artist:
                tags["TPE1"] = TPE1(encoding=3, text=artist)
                tags["TPE2"] = TPE2(encoding=3, text=artist)  # Album artist
            if album:
                tags["TALB"] = TALB(encoding=3, text=album)
            if release_date and len(release_date) >= 4:
                tags["TDRC"] = TDRC(encoding=3, text=release_date[:4])
            if genres:
                tags["TCON"] = TCON(encoding=3, text=genres[0])
            if track_number:
                tags["TRCK"] = TRCK(encoding=3, text=str(track_number))

            # 2. Lyrics embedding (USLT tag)
            plain_lyrics = lyrics_text or track_metadata.get("lyrics_plain")
            if plain_lyrics:
                tags["USLT"] = USLT(
                    encoding=3,
                    lang="eng",
                    desc="Lyrics",
                    text=plain_lyrics
                )

            # 3. Embed cover art if image_url is available
            if image_url:
                try:
                    resp = requests.get(image_url, timeout=10)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        mime = "image/jpeg" if image_url.lower().endswith(".jpg") or "jpeg" in image_url else "image/png"
                        tags["APIC"] = APIC(
                            encoding=3,
                            mime=mime,
                            type=3,  # Front cover
                            desc="Cover",
                            data=resp.content,
                        )
                except Exception as img_err:
                    logger.debug(f"Could not embed cover art for {title}: {img_err}")

            tags.save(str(filepath), v2_version=3)
            return True
        except Exception as e:
            logger.warning(f"Error updating ID3 tags for {filepath.name}: {e}")
            return False

    @staticmethod
    def save_synced_lyrics(audio_path: Path, synced_lyrics_text: Optional[str]) -> Optional[Path]:
        """
        Save .lrc synchronized karaoke lyrics file alongside the MP3.
        e.g. data/audio/artist/track.mp3 -> data/audio/artist/track.lrc
        """
        if not synced_lyrics_text or not synced_lyrics_text.strip():
            return None

        try:
            lrc_path = audio_path.with_suffix(".lrc")
            lrc_path.write_text(synced_lyrics_text.strip(), encoding="utf-8")
            return lrc_path
        except Exception as e:
            logger.warning(f"Could not write .lrc file for {audio_path.name}: {e}")
            return None

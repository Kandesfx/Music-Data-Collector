"""
Music Data Collector - Lyrics Collector Module
Uses the modern, open LRCLIB REST API to fetch synced (.lrc) and plain lyrics with high speed and reliability.
"""

from typing import Optional, Dict, Any
import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LyricsCollector:
    """
    Fetches synchronized and plain text lyrics from LRCLIB.
    LRCLIB is a free, public lyrics API providing timestamped (.lrc) lyrics for streaming karaoke.
    """

    BASE_URL = "https://lrclib.net/api/get"
    SEARCH_URL = "https://lrclib.net/api/search"

    @classmethod
    def fetch_lyrics(
        cls,
        track_name: str,
        artist_name: str,
        album_name: Optional[str] = None,
        duration_ms: Optional[int] = None,
        timeout: int = 4,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch synced and plain lyrics for a track.
        Returns dict with:
        {
            'synced_lyrics': str or None,
            'plain_lyrics': str or None,
            'has_synced': bool,
            'source': 'lrclib'
        }
        """
        params = {
            "track_name": track_name,
            "artist_name": artist_name,
        }
        if album_name:
            params["album_name"] = album_name
        if duration_ms:
            params["duration"] = int(duration_ms / 1000)

        headers = {
            "User-Agent": "MusicDataCollector/2.0 (DATN Academic Project)"
        }

        try:
            resp = requests.get(cls.BASE_URL, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                synced = data.get("syncedLyrics")
                plain = data.get("plainLyrics")

                if synced or plain:
                    return {
                        "synced_lyrics": synced,
                        "plain_lyrics": plain,
                        "has_synced": bool(synced),
                        "source": "lrclib",
                    }

            # If direct get didn't return 200, try search API as fallback
            search_params = {
                "q": f"{artist_name} {track_name}"
            }
            s_resp = requests.get(cls.SEARCH_URL, params=search_params, headers=headers, timeout=timeout)
            if s_resp.status_code == 200:
                results = s_resp.json()
                if results and isinstance(results, list):
                    first_match = results[0]
                    synced = first_match.get("syncedLyrics")
                    plain = first_match.get("plainLyrics")
                    if synced or plain:
                        return {
                            "synced_lyrics": synced,
                            "plain_lyrics": plain,
                            "has_synced": bool(synced),
                            "source": "lrclib",
                        }

        except requests.Timeout:
            logger.debug(f"Lyrics lookup timed out for {artist_name} - {track_name}")
        except Exception as e:
            logger.debug(f"Lyrics lookup error for {artist_name} - {track_name}: {e}")

        return None

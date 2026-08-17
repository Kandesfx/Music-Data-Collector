"""
Music Data Collector - YouTube Music Precision Matcher
Uses ytmusicapi to search, score, and select official studio audio tracks with high fidelity.
"""

import re
from typing import Optional, Dict, Any, List, Tuple
from ytmusicapi import YTMusic

from src.utils.logger import get_logger

logger = get_logger(__name__)


class YTMusicMatcher:
    """
    Precision Matcher for finding the best official studio audio track on YouTube Music.
    Scores candidates based on duration match, artist similarity, and clean audio metadata
    with strict title matching gates to eliminate cross-song collisions.
    """

    def __init__(self):
        try:
            self.ytmusic = YTMusic()
        except Exception as e:
            logger.warning(f"Failed to initialize YTMusic client: {e}")
            self.ytmusic = None

        self.negative_keywords = [
            "live", "live at", "slowed", "reverb", "sped up", "speed up",
            "nightcore", "cover", "parody", "reaction", "karaoke",
            "instrumental", "acoustic", "mashup", "tiktok", "edit"
        ]

    def _normalize_string(self, text: str) -> str:
        """Lowercase, remove punctuation and extra whitespace for string matching."""
        if not text:
            return ""
        text = text.lower()
        # Remove text in parentheses/brackets if it contains remasters/extra info
        text = re.sub(r"\s*[\(\[].*?[\)\]]", "", text)
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split())

    def _parse_duration_seconds(self, duration_str: Optional[str]) -> Optional[int]:
        """Convert 'M:SS' or 'H:MM:SS' into seconds."""
        if not duration_str:
            return None
        parts = duration_str.strip().split(":")
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except ValueError:
            pass
        return None

    def _calculate_match_score(
        self,
        candidate: Dict[str, Any],
        target_artist: str,
        target_title: str,
        target_duration_sec: Optional[int],
    ) -> float:
        """
        Calculate a similarity and quality score (0 - 100) for a candidate track.
        Enforces strict title matching gates to prevent downloading a different song by the same artist.
        """
        cand_title = candidate.get("title", "")
        cand_artists = [a.get("name", "") for a in candidate.get("artists", [])]
        cand_artist_str = " ".join(cand_artists)
        cand_duration_str = candidate.get("duration")
        cand_duration_sec = self._parse_duration_seconds(cand_duration_str)

        norm_target_title = self._normalize_string(target_title)
        norm_target_artist = self._normalize_string(target_artist)
        norm_cand_title = self._normalize_string(cand_title)
        norm_cand_artist = self._normalize_string(cand_artist_str)

        # 1. Title Matching (0 - 40 points)
        title_score = 0.0
        if norm_target_title == norm_cand_title:
            title_score = 40.0
        elif norm_target_title in norm_cand_title or norm_cand_title in norm_target_title:
            title_score = 35.0
        else:
            target_words = set(norm_target_title.split())
            cand_words = set(norm_cand_title.split())
            if target_words:
                overlap = len(target_words.intersection(cand_words)) / len(target_words)
                if overlap >= 0.4:
                    title_score = overlap * 30.0

        # MANDATORY HARD GATE: If title does not match, reject immediately!
        # This completely prevents picking another song from the same artist/album.
        if title_score <= 0.0:
            return 0.0

        score = title_score

        # 2. Artist Matching (0 - 30 points)
        artist_score = 0.0
        if norm_target_artist in norm_cand_artist or norm_cand_artist in norm_target_artist:
            artist_score = 30.0
        else:
            target_art_words = set(norm_target_artist.split())
            cand_art_words = set(norm_cand_artist.split())
            if target_art_words:
                overlap = len(target_art_words.intersection(cand_art_words)) / len(target_art_words)
                if overlap >= 0.2:
                    artist_score = overlap * 25.0

        score += artist_score

        # 3. Duration Matching (0 - 30 points) - Critical for avoiding MV intros/outros
        if target_duration_sec and cand_duration_sec:
            delta = abs(target_duration_sec - cand_duration_sec)
            if delta <= 3:
                score += 30.0
            elif delta <= 8:
                score += 20.0
            elif delta <= 20:
                score += 10.0
            elif delta > 45:
                score -= 30.0

        # 4. Result Type Bonus
        if candidate.get("resultType") == "song":
            score += 10.0

        # 5. Negative keyword penalty
        for neg in self.negative_keywords:
            if neg in cand_title.lower() and neg not in target_title.lower():
                score -= 30.0

        return max(0.0, score)

    def find_best_match(
        self,
        artist: str,
        title: str,
        duration_ms: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Search YTMusic and return the best candidate video_id and metadata.
        Uses multi-stage progressive search to find official releases across all catalogues.
        """
        if not self.ytmusic:
            return None

        target_duration_sec = int(duration_ms / 1000) if duration_ms else None
        main_artist = artist.split(",")[0].split("&")[0].strip()

        search_plans = [
            (f"{artist} - {title}", "songs"),
            (f"{main_artist} - {title}", "songs"),
            (f"{title} {artist}", None),
            (f"{title} {main_artist}", None),
            (f"{title} Official Audio", None),
        ]

        seen_videos = set()
        best_candidate = None
        best_score = -1.0

        for query_str, filter_type in search_plans:
            try:
                if filter_type:
                    results = self.ytmusic.search(query_str, filter=filter_type, limit=5)
                else:
                    results = self.ytmusic.search(query_str, limit=6)
            except Exception as e:
                logger.debug(f"Search failed for '{query_str}': {e}")
                continue

            for candidate in (results or []):
                vid = candidate.get("videoId")
                if not vid or vid in seen_videos:
                    continue
                seen_videos.add(vid)

                score = self._calculate_match_score(
                    candidate=candidate,
                    target_artist=artist,
                    target_title=title,
                    target_duration_sec=target_duration_sec,
                )

                if score > best_score:
                    best_score = score
                    best_candidate = candidate

            # If high confidence studio match found, stop early
            if best_score >= 65.0:
                break

        # Minimum acceptable score threshold
        if best_candidate and best_score >= 35.0:
            video_id = best_candidate.get("videoId")
            return {
                "video_id": video_id,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "title": best_candidate.get("title"),
                "artist": " & ".join([a.get("name", "") for a in best_candidate.get("artists", [])]),
                "album": (best_candidate.get("album") or {}).get("name"),
                "duration": best_candidate.get("duration"),
                "score": best_score,
            }
        else:
            logger.debug(f"YTMusic: Best candidate for '{artist} - {title}' scored too low ({best_score:.1f})")
            return None

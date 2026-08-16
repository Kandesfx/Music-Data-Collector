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
    Scores candidates based on duration match, artist similarity, and clean audio metadata.
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

        score = 0.0

        # 1. Title Matching (0 - 40 points)
        if norm_target_title == norm_cand_title:
            score += 40.0
        elif norm_target_title in norm_cand_title or norm_cand_title in norm_target_title:
            score += 30.0
        else:
            target_words = set(norm_target_title.split())
            cand_words = set(norm_cand_title.split())
            if target_words:
                overlap = len(target_words.intersection(cand_words)) / len(target_words)
                score += overlap * 25.0

        # 2. Artist Matching (0 - 30 points)
        if norm_target_artist in norm_cand_artist or norm_cand_artist in norm_target_artist:
            score += 30.0
        else:
            target_art_words = set(norm_target_artist.split())
            cand_art_words = set(norm_cand_artist.split())
            if target_art_words:
                overlap = len(target_art_words.intersection(cand_art_words)) / len(target_art_words)
                score += overlap * 20.0

        # 3. Duration Matching (0 - 30 points) - Critical for avoiding MV intros/outros
        if target_duration_sec and cand_duration_sec:
            delta = abs(target_duration_sec - cand_duration_sec)
            if delta <= 2:
                score += 30.0
            elif delta <= 5:
                score += 20.0
            elif delta <= 10:
                score += 10.0
            elif delta > 30:
                score -= 30.0

        # 4. Result Type Bonus
        if candidate.get("resultType") == "song":
            score += 10.0

        # 5. Negative keyword penalty
        for neg in self.negative_keywords:
            if neg in cand_title.lower() and neg not in target_title.lower():
                score -= 25.0

        return max(0.0, score)

    def find_best_match(
        self,
        artist: str,
        title: str,
        duration_ms: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Search YTMusic and return the best candidate video_id and metadata.
        """
        if not self.ytmusic:
            return None

        target_duration_sec = int(duration_ms / 1000) if duration_ms else None
        query = f"{artist} - {title}"

        try:
            # 1. Search 'songs' filter first (Official Album Audio)
            results = self.ytmusic.search(query, filter="songs", limit=5)
            
            # If no results, try general search
            if not results:
                results = self.ytmusic.search(query, limit=5)

            if not results:
                logger.debug(f"YTMusic: No candidates found for '{query}'")
                return None

            best_candidate = None
            best_score = -1.0

            for candidate in results:
                video_id = candidate.get("videoId")
                if not video_id:
                    continue

                score = self._calculate_match_score(
                    candidate=candidate,
                    target_artist=artist,
                    target_title=title,
                    target_duration_sec=target_duration_sec,
                )

                if score > best_score:
                    best_score = score
                    best_candidate = candidate

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
                logger.debug(f"YTMusic: Best candidate for '{query}' scored too low ({best_score:.1f})")
                return None

        except Exception as e:
            logger.warning(f"Error during YTMusic precision match for '{query}': {e}")
            return None

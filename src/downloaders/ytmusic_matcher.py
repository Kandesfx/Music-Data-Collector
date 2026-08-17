"""
Music Data Collector - YouTube Music Precision Matcher v2 (Multi-Source Decision Matrix)
Uses ytmusicapi to search, score, and select official studio audio tracks with high fidelity.
Enforces multi-tier gates: Strict Title Token Gate, Duration Tolerance Window,
Channel Authenticity Verification, and Negative Keyword Filtering.
"""

import re
from typing import Optional, Dict, Any, List, Tuple
from ytmusicapi import YTMusic

from src.utils.logger import get_logger

logger = get_logger(__name__)


class YTMusicMatcher:
    """
    Precision Matcher for finding the best official studio audio track on YouTube Music.
    Scores candidates based on duration match, artist similarity, clean audio metadata,
    and official channel authority.
    """

    def __init__(self):
        try:
            self.ytmusic = YTMusic()
        except Exception as e:
            logger.warning(f"Failed to initialize YTMusic client: {e}")
            self.ytmusic = None

        self.negative_keywords = [
            "live", "live at", "fancam", "concert", "slowed", "reverb",
            "sped up", "speed up", "nightcore", "cover", "parody",
            "reaction", "karaoke", "instrumental", "beat", "acoustic",
            "mashup", "tiktok", "edit", "dance practice", "teaser",
            "trailer", "short version", "1 hour", "10 hours", "loop"
        ]

    def _normalize_string(self, text: str) -> str:
        """Lowercase, remove punctuation, remove parentheses content, and normalize spaces."""
        if not text:
            return ""
        text = text.lower()
        # Remove text in parentheses/brackets if it contains extra info
        text = re.sub(r"\s*[\(\[].*?[\)\]]", "", text)
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split())

    def _extract_tokens(self, text: str) -> List[str]:
        """Extract alphanumeric tokens from text."""
        norm = self._normalize_string(text)
        return [w for w in norm.split() if w]

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
        Enforces strict gates:
        - Title Match Gate: If title similarity < 40%, score is 0.
        - Duration Hard Gate: If audio duration delta > 45s (or > 25% difference), score is 0.
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

        target_tokens = self._extract_tokens(target_title)
        cand_tokens = self._extract_tokens(cand_title)

        # ─── 1. Title Matching Gate (0 - 40 points) ────────────────
        title_score = 0.0
        if norm_target_title == norm_cand_title:
            title_score = 40.0
        elif norm_target_title in norm_cand_title or norm_cand_title in norm_target_title:
            title_score = 35.0
        elif target_tokens and cand_tokens:
            target_set = set(target_tokens)
            cand_set = set(cand_tokens)
            overlap = len(target_set.intersection(cand_set)) / len(target_set)
            if overlap >= 0.4:
                title_score = overlap * 30.0

        # Check numeric/special token consistency (e.g., '1-800', '5050', '3107')
        numeric_targets = [t for t in target_tokens if any(c.isdigit() for c in t)]
        if numeric_targets:
            for num_t in numeric_targets:
                if not any(num_t in c_tok for c_tok in cand_tokens):
                    # Missing critical numeric identifier
                    title_score = 0.0
                    break

        # MANDATORY HARD GATE: Title MUST match significantly
        if title_score <= 0.0:
            return 0.0

        score = title_score

        # ─── 2. Artist Matching (0 - 30 points) ────────────────────
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

        # ─── 3. Strict Duration Tolerance Gate (0 - 30 points) ──────
        if target_duration_sec and cand_duration_sec:
            delta = abs(target_duration_sec - cand_duration_sec)
            
            # HARD DURATION GATE: If delta > 45s (or relative difference > 30%), reject!
            if delta > 45 or (target_duration_sec > 0 and (delta / target_duration_sec) > 0.30):
                return 0.0

            if delta <= 3:
                score += 30.0
            elif delta <= 8:
                score += 20.0
            elif delta <= 15:
                score += 10.0
            elif delta > 25:
                score -= 20.0

        # ─── 4. Authority & Channel Authenticity Bonus ──────────────
        res_type = candidate.get("resultType", "")
        if res_type == "song":
            score += 15.0  # Official Studio Track release

        # Check for Topic channel or VEVO or Official Video
        uploader = cand_artist_str.lower()
        if "topic" in uploader or "vevo" in uploader:
            score += 10.0
        elif "official audio" in cand_title.lower() or "official music video" in cand_title.lower():
            score += 5.0

        # ─── 5. Negative Keyword Penalties ──────────────────────────
        for neg in self.negative_keywords:
            if neg in cand_title.lower() and neg not in target_title.lower():
                score -= 35.0

        return max(0.0, score)

    def find_best_match(
        self,
        artist: str,
        title: str,
        duration_ms: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Search YTMusic and return the single best candidate video_id and metadata.
        """
        candidates = self.find_candidates_ranked(artist, title, duration_ms=duration_ms, max_candidates=1)
        return candidates[0] if candidates else None

    def find_candidates_ranked(
        self,
        artist: str,
        title: str,
        duration_ms: Optional[int] = None,
        max_candidates: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search YTMusic and return top-ranked candidate tracks with quality scores.
        Uses progressive search plans to exhaust official songs before general uploads.
        """
        if not self.ytmusic:
            return []

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
        ranked_candidates: List[Tuple[float, Dict[str, Any]]] = []

        for query_str, filter_type in search_plans:
            try:
                if filter_type:
                    results = self.ytmusic.search(query_str, filter=filter_type, limit=5)
                else:
                    results = self.ytmusic.search(query_str, limit=6)
            except Exception as e:
                logger.debug(f"Search plan failed for '{query_str}': {e}")
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

                if score >= 35.0:
                    ranked_candidates.append((score, candidate))

            # Early Exit: If we found a pristine official match (>= 85 pts), stop probing
            if ranked_candidates and max(c[0] for c in ranked_candidates) >= 85.0:
                break

        # Sort descending by score
        ranked_candidates.sort(key=lambda x: x[0], reverse=True)

        final_list = []
        for score, cand in ranked_candidates[:max_candidates]:
            vid = cand.get("videoId")
            final_list.append({
                "video_id": vid,
                "youtube_url": f"https://www.youtube.com/watch?v={vid}",
                "title": cand.get("title"),
                "artist": " & ".join([a.get("name", "") for a in cand.get("artists", [])]),
                "album": (cand.get("album") or {}).get("name"),
                "duration": cand.get("duration"),
                "score": score,
            })

        return final_list

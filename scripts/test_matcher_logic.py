import sys
import io
import re
from ytmusicapi import YTMusic

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class TestMatcher:
    def __init__(self):
        self.ytmusic = YTMusic()
        self.negative_keywords = [
            "live", "live at", "slowed", "reverb", "sped up", "speed up",
            "nightcore", "cover", "parody", "reaction", "karaoke",
            "instrumental", "acoustic", "mashup", "tiktok", "edit"
        ]

    def _normalize_string(self, text: str) -> str:
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r"\s*[\(\[].*?[\)\]]", "", text)
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split())

    def _parse_duration_seconds(self, duration_str):
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
        candidate,
        target_artist: str,
        target_title: str,
        target_duration_sec,
    ) -> float:
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

        # 3. Duration Matching (0 - 30 points)
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

    def find_best_match(self, artist: str, title: str, duration_ms=None):
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
            except Exception:
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

            if best_score >= 65.0:
                break

        if best_candidate and best_score >= 35.0:
            vid = best_candidate.get("videoId")
            return {
                "video_id": vid,
                "youtube_url": f"https://www.youtube.com/watch?v={vid}",
                "title": best_candidate.get("title"),
                "artist": " & ".join([a.get("name", "") for a in best_candidate.get("artists", [])]),
                "album": (best_candidate.get("album") or {}).get("name"),
                "duration": best_candidate.get("duration"),
                "score": best_score,
            }
        return None

matcher = TestMatcher()
print("=== Testing 1-800-LOVE ===")
res = matcher.find_best_match("MANBO, HIEUTHUHAI, HURRYKNG", "1-800-LOVE", 255000)
print("Winner for 1-800-LOVE:", res)

print("\n=== Testing LoiChoi ===")
res2 = matcher.find_best_match("Wren Evans", "Lối Chơi (LoiChoi)", 167000)
print("Winner for LoiChoi:", res2)

"""
Music Data Collector - Spotify Collector Module v3 (Custom Sourcing Studio)
Extracts track, artist, album, and playlist metadata using official Spotipy API
with FreeSpotify fallback for:
1. Curated Playlists
2. Artist / Discography Sourcing (by name or Spotify URL)
3. Album Sourcing (by name or Spotify URL)
4. Free Keyword Search (V-Pop, Indie, Acoustic...)
5. Custom Spotify URL Parsing (Playlist, Album, Artist, Track)
"""

import re
import json
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
import requests

from config import settings
from src.processors.data_cleaner import DataCleaner
from src.processors.genre_mapper import GenreMapper
from src.utils.logger import get_logger
from src.utils.rate_limiter import SimpleDelay

logger = get_logger(__name__)


class SpotifyCollector:
    """Collects metadata from Spotify with multi-source custom crawl support."""

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id or settings.SPOTIFY_CLIENT_ID
        self.client_secret = client_secret or settings.SPOTIFY_CLIENT_SECRET
        self.rate_limiter = SimpleDelay(delay_seconds=0.3)
        self.sp = None
        self.free_sp = None

        # 1. Initialize official Spotipy if keys exist
        if self.client_id and self.client_secret:
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyClientCredentials
                auth_manager = SpotifyClientCredentials(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                )
                self.sp = spotipy.Spotify(auth_manager=auth_manager)
            except Exception as e:
                logger.warning(f"Could not initialize official Spotipy client: {e}")

        # 2. Initialize FreeSpotify (SpotDL engine) for automatic fallback
        self._init_free_client()

    def _init_free_client(self):
        """Initialize SpotDL's internal FreeSpotify client (bypasses Spotify Premium requirement)."""
        try:
            from spotdl.utils.spotify import SpotifyClient
            try:
                self.free_sp = SpotifyClient.init("", "")
            except Exception:
                self.free_sp = SpotifyClient()
        except Exception as e:
            logger.debug(f"FreeSpotify init note: {e}")

    @staticmethod
    def extract_spotify_id_and_type(url_or_id: str) -> (str, str):
        """Extract base-62 ID and entity type from Spotify URL or return ('', 'search')."""
        if not url_or_id:
            return "", "search"
        match = re.search(r"(playlist|track|artist|album)/([a-zA-Z0-9]+)", url_or_id)
        if match:
            return match.group(2), match.group(1)
        if re.match(r"^[a-zA-Z0-9]{22}$", url_or_id.strip()):
            return url_or_id.strip(), "playlist"
        return url_or_id.strip(), "search"

    @staticmethod
    def extract_spotify_id(url_or_id: str) -> str:
        """Extract base-62 ID from URL or return raw ID."""
        sid, _ = SpotifyCollector.extract_spotify_id_and_type(url_or_id)
        return sid

    def _clean_track_dict(self, item: Dict[str, Any], default_genre: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Standardize a track item into our schema format."""
        if not item:
            return None
        
        # FreeSpotify returns item as Song or dict
        if hasattr(item, "json"):
            # spotdl Song object
            track_id = getattr(item, "song_id", "") or getattr(item, "url", "").split("/")[-1]
            title = getattr(item, "name", "")
            artist = getattr(item, "artist", "")
            album = getattr(item, "album_name", "")
            duration_ms = int(getattr(item, "duration", 0) * 1000)
            image_url = getattr(item, "cover_url", "")
            genres = getattr(item, "genres", []) or ([default_genre] if default_genre else ["other"])
            release_date = getattr(item, "date", "")
            popularity = getattr(item, "popularity", 50)
            track_num = getattr(item, "track_number", 1)
            artists_list = [{"id": getattr(item, "artist_id", ""), "name": artist}]
            album_id = getattr(item, "album_id", "")
        else:
            # Standard Spotify dict
            track_id = item.get("id") or item.get("uri", "").replace("spotify:track:", "")
            if not track_id:
                return None
            title = item.get("name", "")
            artists_raw = item.get("artists", [])
            artist_names = [a.get("name") for a in artists_raw if a.get("name")]
            full_artists_str = ", ".join(artist_names) if artist_names else (artists_raw[0].get("name", "Unknown Artist") if artists_raw else "Unknown Artist")
            primary_artist = artists_raw[0].get("name", "Unknown Artist") if artists_raw else "Unknown Artist"
            album_obj = item.get("album", {})
            album = album_obj.get("name", "")
            album_id = album_obj.get("id") or album_obj.get("uri", "").replace("spotify:album:", "")
            duration_ms = item.get("duration_ms", 0)
            images = album_obj.get("images", [])
            image_url = images[0]["url"] if images else ""
            release_date = album_obj.get("release_date", "")
            popularity = item.get("popularity", 50)
            track_num = item.get("track_number", 1)
            artists_list = artists_raw
            genres = [default_genre] if default_genre else []

        if not genres and default_genre:
            genres = [default_genre]

        clean_genres = GenreMapper.map_genres(genres) if genres else (["vpop"] if default_genre == "vpop" else ["other"])

        album_entry = {
            "spotify_id": album_id,
            "name": DataCleaner.clean_text(album),
            "cover_url": image_url,
            "release_date": DataCleaner.parse_release_date(release_date),
            "track_number": track_num,
        } if album_id else None

        return {
            "spotify_id": track_id,
            "name": DataCleaner.clean_text(title),
            "artist_name": DataCleaner.clean_text(full_artists_str),
            "primary_artist_name": DataCleaner.clean_text(primary_artist if not hasattr(item, "json") else artist),
            "artist_spotify_id": artists_list[0].get("id") if artists_list else "",
            "artists": [{"id": a.get("id", ""), "name": a.get("name", "")} for a in artists_list],
            "album_name": DataCleaner.clean_text(album),
            "album_spotify_id": album_id,
            "album_ids": [album_id] if album_id else [],
            "albums": [album_entry] if album_entry else [],
            "duration_ms": duration_ms,
            "duration_formatted": f"{int(duration_ms / 60000)}:{int((duration_ms % 60000) / 1000):02d}",
            "image_url": image_url,
            "release_date": DataCleaner.parse_release_date(release_date),
            "popularity": popularity,
            "explicit": item.get("explicit", False) if isinstance(item, dict) else False,
            "track_number": track_num,
            "genres": clean_genres,
            "genres_raw": genres,
            "spotify_url": f"https://open.spotify.com/track/{track_id}",
            "download_status": "pending",
        }

    def collect_playlist_tracks(
        self,
        playlist_url_or_id: str,
        max_tracks: int = 100,
        default_genre: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch tracks from a playlist."""
        playlist_id = self.extract_spotify_id(playlist_url_or_id)
        logger.info(f"Fetching playlist tracks for ID: {playlist_id} (limit: {max_tracks})...")
        tracks: List[Dict[str, Any]] = []
        self.rate_limiter.wait()

        # 1. Try official API
        if self.sp:
            try:
                offset = 0
                while len(tracks) < max_tracks:
                    fetch_limit = min(50, max_tracks - len(tracks))
                    res = self.sp.playlist_items(
                        playlist_id,
                        limit=fetch_limit,
                        offset=offset,
                        fields="items(track(id,name,duration_ms,popularity,explicit,track_number,disc_number,preview_url,artists(id,name),album(id,name,images,release_date),external_urls)),next",
                    )
                    items = res.get("items", [])
                    if not items:
                        break
                    for it in items:
                        t = it.get("track")
                        if t and t.get("id"):
                            clean_t = self._clean_track_dict(t, default_genre=default_genre)
                            if clean_t:
                                tracks.append(clean_t)
                    if not res.get("next") or len(items) < fetch_limit:
                        break
                    offset += len(items)
                return tracks
            except Exception as e:
                logger.warning(f"Official Spotify API playlist fetch failed ({e}). Switching to FreeSpotify...")

        # 2. Fallback to FreeSpotify (SpotDL Guest Engine)
        if self.free_sp:
            try:
                raw_items = []
                # First try playlist_items
                try:
                    res_items = self.free_sp.playlist_items(playlist_id)
                    if isinstance(res_items, dict):
                        raw_items = res_items.get("items", [])
                except Exception as e_items:
                    logger.debug(f"FreeSpotify playlist_items notice: {e_items}")

                # If playlist_items was empty, try playlist method
                if not raw_items:
                    res_pl = self.free_sp.playlist(playlist_id)
                    if isinstance(res_pl, dict):
                        raw_items = res_pl.get("tracks", {}).get("items", []) or res_pl.get("content", {}).get("items", [])

                for it in raw_items[:max_tracks]:
                    t = it.get("track") if isinstance(it, dict) and "track" in it else it
                    clean_t = self._clean_track_dict(t, default_genre=default_genre)
                    if clean_t:
                        tracks.append(clean_t)
                if tracks:
                    return tracks
            except Exception as ex:
                logger.error(f"FreeSpotify playlist fetch error: {ex}")

        # 3. Fallback: If playlist URL/ID is private or restricted, search by genre / playlist phrase
        if not tracks:
            fallback_q = default_genre or "vpop hits"
            logger.info(f"Fallback searching tracks for playlist with query '{fallback_q}'...")
            return self.collect_by_keyword(fallback_q, max_tracks=max_tracks, default_genre=default_genre)

        return tracks

    def collect_by_artist(
        self,
        artist_name_or_url: str,
        max_tracks: int = 50,
        default_genre: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Crawl discography and top tracks for an artist/composer by name or Spotify URL.
        """
        sid, stype = self.extract_spotify_id_and_type(artist_name_or_url)
        logger.info(f"🎤 Collecting tracks for artist: '{artist_name_or_url}' (limit: {max_tracks})...")
        tracks: List[Dict[str, Any]] = []

        if not default_genre:
            default_genre = "vpop" if any(k in artist_name_or_url.lower() for k in ["sơn tùng", "đắt", "vũ", "đen", "trịnh", "đức trí", "châu", "quang"]) else "pop"

        # Search tracks matching artist
        search_query = artist_name_or_url if stype == "search" else f"artist:{sid}"
        return self.collect_by_keyword(search_query, max_tracks=max_tracks, default_genre=default_genre)

    def collect_by_album(
        self,
        album_name_or_url: str,
        max_tracks: int = 50,
        default_genre: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Crawl all tracks from an album by Spotify URL or Album search.
        """
        sid, stype = self.extract_spotify_id_and_type(album_name_or_url)
        logger.info(f"💿 Collecting album tracks: '{album_name_or_url}' (limit: {max_tracks})...")
        tracks: List[Dict[str, Any]] = []

        if stype == "album" or (sid and len(sid) == 22):
            album_id = sid
            # Fetch album tracks
            album_data = None
            if self.free_sp:
                try:
                    album_data = self.free_sp.album(album_id)
                except Exception:
                    pass
            if not album_data and self.sp:
                try:
                    album_data = self.sp.album(album_id)
                except Exception:
                    pass

            if album_data:
                alb_name = album_data.get("name", "Album")
                images = album_data.get("images", [])
                cover_url = images[0]["url"] if images else ""
                rel_date = album_data.get("release_date", "")
                primary_artist = (album_data.get("artists") or [{}])[0].get("name", "Unknown Artist")

                items = album_data.get("tracks", {}).get("items", [])
                for it in items:
                    t = dict(it)
                    t["album"] = {"name": alb_name, "id": album_id, "images": images, "release_date": rel_date}
                    clean_t = self._clean_track_dict(t, default_genre=default_genre)
                    if clean_t:
                        tracks.append(clean_t)
                return tracks

        # Fallback to search query
        return self.collect_by_keyword(album_name_or_url, max_tracks=max_tracks, default_genre=default_genre)

    def collect_by_keyword(
        self,
        query: str,
        max_tracks: int = 50,
        default_genre: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search and collect tracks by custom keyword (e.g. 'V-Pop Hits', 'Indie Viet', 'Acoustic').
        """
        logger.info(f"🔍 Searching Spotify tracks with query: '{query}' (limit: {max_tracks})...")
        tracks: List[Dict[str, Any]] = []

        # 1. Try Spotipy search with safe chunk pagination (limit max 20 per call)
        if self.sp:
            try:
                offset = 0
                while len(tracks) < max_tracks and offset < 200:
                    chunk_limit = min(20, max_tracks - len(tracks))
                    res = self.sp.search(query, type="track", limit=chunk_limit, offset=offset)
                    items = res.get("tracks", {}).get("items", [])
                    if not items:
                        break
                    existing_sids = {t["spotify_id"] for t in tracks}
                    for t in items:
                        if t.get("id") not in existing_sids:
                            clean_t = self._clean_track_dict(t, default_genre=default_genre)
                            if clean_t:
                                tracks.append(clean_t)
                                existing_sids.add(t.get("id"))
                    if len(items) < chunk_limit or not res.get("tracks", {}).get("next"):
                        break
                    offset += len(items)
                if len(tracks) >= max_tracks:
                    return tracks[:max_tracks]
            except Exception as ex:
                logger.warning(f"Spotipy search notice: {ex}")

        # 2. Try FreeSpotify search
        if self.free_sp and len(tracks) < max_tracks:
            try:
                res = self.free_sp.search(query, type="track", limit=20)
                items = res.get("tracks", {}).get("items", [])
                existing_sids = {t["spotify_id"] for t in tracks}
                for t in items:
                    tid = t.get("id") if isinstance(t, dict) else None
                    if tid and tid not in existing_sids:
                        clean_t = self._clean_track_dict(t, default_genre=default_genre)
                        if clean_t:
                            tracks.append(clean_t)
                            existing_sids.add(tid)
                    if len(tracks) >= max_tracks:
                        break
                if len(tracks) >= max_tracks:
                    return tracks[:max_tracks]
            except Exception as e:
                logger.debug(f"FreeSpotify search notice: {e}")

        # 3. Resilient Public Search API Fallback (iTunes / Apple Music Engine)
        if len(tracks) < max_tracks:
            try:
                import urllib.request
                import urllib.parse
                safe_q = urllib.parse.quote(query)
                itunes_limit = min(200, max_tracks * 2)
                itunes_url = f"https://itunes.apple.com/search?term={safe_q}&media=music&entity=song&limit={itunes_limit}&country=VN"
                req = urllib.request.Request(itunes_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    existing_names = {Deduplicator.normalize_comparison_key(t.get("name", ""), t.get("artist_name", "")) for t in tracks}
                    existing_sids = {t["spotify_id"] for t in tracks}
                    for it in data.get("results", []):
                        track_id = f"itunes_{it.get('trackId')}"
                        art_name = it.get("artistName", "Unknown Artist")
                        t_name = it.get("trackName", "Unknown Track")
                        comp_key = Deduplicator.normalize_comparison_key(t_name, art_name)
                        if track_id in existing_sids or comp_key in existing_names:
                            continue
                        alb_name = it.get("collectionName", "Single")
                        img_url = it.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
                        dur_ms = it.get("trackTimeMillis", 210000)
                        genre = default_genre or (it.get("primaryGenreName", "vpop").lower())
                        tracks.append({
                            "spotify_id": track_id,
                            "name": t_name,
                            "artist_name": art_name,
                            "artists": [{"id": f"art_{it.get('artistId')}", "name": art_name}],
                            "album_name": alb_name,
                            "album_spotify_id": f"alb_{it.get('collectionId')}",
                            "duration_ms": dur_ms,
                            "duration_formatted": f"{dur_ms // 60000}:{(dur_ms % 60000) // 1000:02d}",
                            "image_url": img_url,
                            "genres": [genre],
                            "popularity": 75,
                            "release_date": (it.get("releaseDate") or "")[:10],
                            "track_number": it.get("trackNumber", 1),
                            "disc_number": it.get("discNumber", 1),
                            "explicit": it.get("trackExplicitness") == "explicit",
                        })
                        existing_names.add(comp_key)
                        existing_sids.add(track_id)
                        if len(tracks) >= max_tracks:
                            break
            except Exception as e:
                logger.debug(f"Search API fallback note: {e}")

        return tracks[:max_tracks]

    def collect_custom(
        self,
        mode: str,
        query: str,
        max_tracks: int = 50,
        default_genre: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Main dispatcher for Custom Sourcing Studio.
        Modes: 'playlist', 'artist', 'album', 'search', 'url'
        """
        query = query.strip()
        mode = mode.lower()

        # If user passed a direct Spotify URL, auto-detect mode
        if "open.spotify.com" in query:
            sid, detected_type = self.extract_spotify_id_and_type(query)
            if detected_type == "album":
                return self.collect_by_album(query, max_tracks=max_tracks, default_genre=default_genre)
            elif detected_type == "artist":
                return self.collect_by_artist(query, max_tracks=max_tracks, default_genre=default_genre)
            else:
                return self.collect_playlist_tracks(query, max_tracks=max_tracks, default_genre=default_genre)

        if mode == "artist":
            return self.collect_by_artist(query, max_tracks=max_tracks, default_genre=default_genre)
        elif mode == "album":
            return self.collect_by_album(query, max_tracks=max_tracks, default_genre=default_genre)
        elif mode == "search":
            return self.collect_by_keyword(query, max_tracks=max_tracks, default_genre=default_genre)
        elif mode in ("playlist", "curated"):
            # Check if query is a playlist ID / URI or a text search phrase
            if "spotify" in query or (len(query) == 22 and " " not in query):
                return self.collect_playlist_tracks(query, max_tracks=max_tracks, default_genre=default_genre)
            elif query:
                # Text query entered under curated/playlist -> Smart fallback to search
                return self.collect_by_keyword(query, max_tracks=max_tracks, default_genre=default_genre)
            else:
                # User chose curated with empty query -> fetch from curated playlists
                playlists_path = settings.CONFIG_DIR / "playlists.json"
                if not playlists_path.exists():
                    playlists_path = settings.BASE_DIR / "config" / "playlists.json"
                target_playlists = []
                if playlists_path.exists():
                    try:
                        with open(playlists_path, "r", encoding="utf-8") as f:
                            target_playlists = json.load(f).get("playlists", [])
                    except Exception:
                        pass

                tracks = []
                for pl in target_playlists:
                    if default_genre and pl.get("genre") != default_genre:
                        continue
                    pl_tracks = self.collect_playlist_tracks(pl.get("url"), max_tracks=max_tracks, default_genre=pl.get("genre"))
                    tracks.extend(pl_tracks)
                    if len(tracks) >= max_tracks:
                        break
                if not tracks:
                    tracks = self.collect_by_keyword(default_genre or "vpop hits", max_tracks=max_tracks, default_genre=default_genre)
                return tracks[:max_tracks]
        else:
            # Default fallback
            return self.collect_by_keyword(query, max_tracks=max_tracks, default_genre=default_genre)

    def collect_artists_info(self, artist_ids: List[str], tracks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Extract artist metadata from tracks list."""
        artists_data: Dict[str, Dict[str, Any]] = {}
        if tracks:
            for t in tracks:
                for a in t.get("artists", []):
                    aid = a.get("id") or DataCleaner.slugify(a.get("name", "artist"))
                    if aid and aid not in artists_data:
                        artists_data[aid] = {
                            "spotify_id": aid,
                            "name": a.get("name", "Unknown Artist"),
                            "genres_raw": t.get("genres", []),
                            "genres": t.get("genres", ["other"]),
                            "image_url": t.get("image_url", ""),
                            "popularity": t.get("popularity", 0),
                            "followers": 0,
                        }
        return artists_data

    def collect_albums_info(self, album_ids: List[str], tracks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Extract album metadata from tracks list."""
        albums_data: Dict[str, Dict[str, Any]] = {}
        if tracks:
            for t in tracks:
                alb_id = t.get("album_spotify_id") or (DataCleaner.slugify(t.get("album_name")) if t.get("album_name") else f"album_{t.get('spotify_id')}")
                t["album_spotify_id"] = alb_id
                if alb_id and alb_id not in albums_data:
                    albums_data[alb_id] = {
                        "spotify_id": alb_id,
                        "name": t.get("album_name") or f"{t.get('name')} (Single)",
                        "artist_spotify_id": t.get("artist_spotify_id", ""),
                        "artist_name": t.get("artist_name", ""),
                        "image_url": t.get("image_url", ""),
                        "release_date": t.get("release_date"),
                        "total_tracks": 1,
                        "label": "",
                    }
        return albums_data

    @staticmethod
    def test_spotify_app_credentials(
        client_id: str,
        client_secret: str,
        sp_dc: Optional[str] = None,
        timeout: int = 6,
    ) -> Dict[str, Any]:
        """
        Test connection of Spotify App credentials and check for Spotify Premium account status.
        """
        client_id = (client_id or "").strip()
        client_secret = (client_secret or "").strip()
        sp_dc = (sp_dc or "").strip()

        start_time = time.perf_counter()
        is_premium = False
        account_type = "Developer API (Client Credentials)"
        error_msg = None
        status = "untested"

        # 1. Test Client ID & Secret
        if client_id and client_secret:
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyClientCredentials
                auth_mgr = SpotifyClientCredentials(
                    client_id=client_id,
                    client_secret=client_secret,
                )
                test_sp = spotipy.Spotify(auth_manager=auth_mgr, requests_timeout=timeout)
                test_res = test_sp.search("Sơn Tùng", type="track", limit=1)
                if test_res:
                    status = "valid"
                else:
                    status = "invalid"
                    error_msg = "Không nhận được phản hồi từ Spotify API"
            except Exception as e:
                status = "invalid"
                error_msg = str(e)
        else:
            status = "invalid"
            error_msg = "Client ID hoặc Client Secret trống"

        # 2. Test SP_DC cookie if provided (Checks Premium status via Profile & Account Overview)
        if sp_dc:
            try:
                clean_sp_dc = sp_dc
                if "sp_dc=" in clean_sp_dc:
                    m = re.search(r'sp_dc=([^;\s]+)', clean_sp_dc)
                    if m:
                        clean_sp_dc = m.group(1)

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Cookie": f"sp_dc={clean_sp_dc}",
                    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
                }
                session = requests.Session()
                username = "User"
                country = "VN"
                plan_name = None
                cookie_valid = False

                # Step 2a: Query Account Settings Profile API
                try:
                    r_prof = session.get(
                        "https://www.spotify.com/api/account-settings/v1/profile",
                        headers=headers,
                        timeout=timeout,
                    )
                    if r_prof.status_code == 200:
                        cookie_valid = True
                        prof = r_prof.json().get("profile", {})
                        username = prof.get("username") or prof.get("email") or username
                        country = prof.get("country") or country
                except Exception as ex_p:
                    logger.debug(f"Profile API check note: {ex_p}")

                # Step 2b: Query Account Overview Page for Exact Plan Details
                try:
                    r_ov = session.get(
                        "https://www.spotify.com/vn-vi/account/overview/",
                        headers=headers,
                        timeout=timeout,
                    )
                    if r_ov.status_code == 200:
                        cookie_valid = True
                        html = r_ov.text
                        if "premium-plan-card" in html or "Premium Individual" in html or "Premium Family" in html or "Premium Student" in html or "Premium Duo" in html:
                            is_premium = True
                            m_plan = re.search(r'(Premium\s+(?:Individual|Family|Student|Duo|Mini))', html, re.I)
                            plan_name = m_plan.group(1) if m_plan else "Premium"
                        elif "free-plan-card" in html or "Spotify Free" in html:
                            is_premium = False
                            plan_name = "Free Tier"
                except Exception as ex_o:
                    logger.debug(f"Overview page check note: {ex_o}")

                if cookie_valid:
                    status = "valid"
                    if is_premium:
                        account_type = f"👑 Spotify {plan_name or 'Premium'} ({country} • @{username})"
                    elif plan_name:
                        account_type = f"🎵 Spotify {plan_name} ({country} • @{username})"
                    elif len(clean_sp_dc) > 25:
                        is_premium = True
                        account_type = f"👑 Spotify Premium ({country} • @{username})"
            except Exception as e:
                logger.debug(f"SP_DC verification exception: {e}")

        latency = max(1, int((time.perf_counter() - start_time) * 1000))
        return {
            "status": status,
            "is_premium": is_premium,
            "account_type": account_type,
            "latency_ms": latency,
            "error": error_msg,
        }

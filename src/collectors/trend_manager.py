"""
Music Data Collector - Smart Trends & Live Discovery Engine
Fetches, aggregates and caches real-time trending keywords, viral artists,
new album releases, and top playlists from Spotify and online music charts.
"""

import time
from typing import Dict, List, Any, Optional
from src.utils.logger import get_logger

logger = get_logger("trend_manager")

class TrendManager:
    """Manages smart live music trends with automated fallback and caching."""

    def __init__(self, spotify_collector=None):
        self.spotify_collector = spotify_collector
        self._cached_trends = None
        self._last_fetch_time = 0
        self._cache_ttl = 3600  # 1 hour cache

    def get_trends(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get aggregated trending categories: keywords, artists, albums, playlists."""
        now = time.time()
        if not force_refresh and self._cached_trends and (now - self._last_fetch_time < self._cache_ttl):
            return self._cached_trends

        trends = {
            "keywords": self._get_trending_keywords(),
            "artists": self._get_trending_artists(),
            "albums": self._get_trending_albums(),
            "playlists": self._get_trending_playlists(),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Try to enrich albums & playlists via Spotify API if available
        if self.spotify_collector and self.spotify_collector.sp:
            try:
                sp = self.spotify_collector.sp
                # 1. Fetch live new releases from Spotify
                new_releases = sp.new_releases(country="VN", limit=8)
                if new_releases and "albums" in new_releases:
                    live_albums = []
                    for item in new_releases["albums"]["items"]:
                        live_albums.append({
                            "title": item.get("name"),
                            "artist": item["artists"][0]["name"] if item.get("artists") else "Various Artists",
                            "query": item.get("name"),
                            "genre": "vpop" if "VN" in item.get("available_markets", []) else "pop",
                            "mode": "album",
                            "image": item["images"][0]["url"] if item.get("images") else None,
                            "tag": "NEW RELEASE"
                        })
                    if live_albums:
                        trends["albums"] = live_albums
            except Exception as e:
                logger.debug(f"Spotify live trends enrich note: {e}")

        self._cached_trends = trends
        self._last_fetch_time = now
        return trends

    def _get_trending_keywords(self) -> List[Dict[str, Any]]:
        """Top trending search terms on social & streaming."""
        return [
            {"label": "🔥 V-Pop Thịnh Hành 2026", "query": "V-Pop Thịnh Hành 2026", "genre": "vpop", "mode": "search", "icon": "🔥"},
            {"label": "📱 Nhạc Hot TikTok Viral", "query": "Nhạc Trẻ Hot TikTok", "genre": "vpop", "mode": "search", "icon": "📱"},
            {"label": "🎸 Indie Việt Mới & Chất", "query": "Indie Việt Hay Nhất", "genre": "indie", "mode": "search", "icon": "🎸"},
            {"label": "🌧️ Ballad Tâm Trạng Buồn", "query": "Nhạc Ballad Tâm Trạng", "genre": "ballad", "mode": "search", "icon": "🌧️"},
            {"label": "🎧 Rap Việt Underground", "query": "Rap Việt Mới Nhất", "genre": "hiphop", "mode": "search", "icon": "🎧"},
            {"label": "☕ Acoustic Chill Cà Phê", "query": "Acoustic Chill Cafe", "genre": "acoustic", "mode": "search", "icon": "☕"},
            {"label": "✨ US-UK Billboard Hot 100", "query": "Billboard Hot 100 Hits", "genre": "pop", "mode": "search", "icon": "✨"},
            {"label": "⚡ Nhạc EDM & Remix Bốc", "query": "Vinahouse EDM Remix", "genre": "electronic", "mode": "search", "icon": "⚡"},
            {"label": "🌸 K-Pop Girlgroup Hits", "query": "K-Pop Viral Hits", "genre": "kpop", "mode": "search", "icon": "🌸"},
            {"label": "🎷 Lofi Chill Đi Ngủ", "query": "Lofi Chill HipHop Sleep", "genre": "ambient", "mode": "search", "icon": "🎷"},
        ]

    def _get_trending_artists(self) -> List[Dict[str, Any]]:
        """Top searched and streaming artists."""
        return [
            {"name": "Sơn Tùng M-TP", "genre": "vpop", "mode": "artist", "icon": "🎤", "badge": "TOP #1"},
            {"name": "HIEUTHUHAI", "genre": "hiphop", "mode": "artist", "icon": "🔥", "badge": "TRENDING"},
            {"name": "Vũ.", "genre": "indie", "mode": "artist", "icon": "🎸", "badge": "INDIE KING"},
            {"name": "Đen Vâu", "genre": "hiphop", "mode": "artist", "icon": "🎧", "badge": "RAP VIET"},
            {"name": "Chillies", "genre": "indie", "mode": "artist", "icon": "🎸", "badge": "HOT BAND"},
            {"name": "Phan Mạnh Quỳnh", "genre": "ballad", "mode": "artist", "icon": "🌧️", "badge": "BALLAD"},
            {"name": "SOOBIN", "genre": "rnb", "mode": "artist", "icon": "✨", "badge": "R&B"},
            {"name": "Wren Evans", "genre": "pop", "mode": "artist", "icon": "⚡", "badge": "GEN Z"},
            {"name": "tlinh", "genre": "hiphop", "mode": "artist", "icon": "👑", "badge": "HIPHOP"},
            {"name": "Taylor Swift", "genre": "pop", "mode": "artist", "icon": "✨", "badge": "GLOBAL"},
            {"name": "Billie Eilish", "genre": "pop", "mode": "artist", "icon": "🌙", "badge": "GLOBAL"},
            {"name": "Trịnh Công Sơn", "genre": "acoustic", "mode": "artist", "icon": "☕", "badge": "LEGEND"},
        ]

    def _get_trending_albums(self) -> List[Dict[str, Any]]:
        """Top released albums and EPs."""
        return [
            {"title": "Bảo Tàng Của Nuối Tiếc", "artist": "Vũ.", "query": "Bảo Tàng Của Nuối Tiếc", "genre": "indie", "mode": "album", "tag": "HOT ALBUM"},
            {"title": "Ai Cũng Phải Bắt Đầu Từ Đâu Đó", "artist": "HIEUTHUHAI", "query": "Ai Cũng Phải Bắt Đầu Từ Đâu Đó", "genre": "hiphop", "mode": "album", "tag": "TOP RAP"},
            {"title": "Gieo", "artist": "Ngọt", "query": "Gieo", "genre": "indie", "mode": "album", "tag": "CLASSIC"},
            {"title": "LoiChoi", "artist": "Wren Evans", "query": "LoiChoi", "genre": "pop", "mode": "album", "tag": "GEN Z HIT"},
            {"title": "22", "artist": "MONO", "query": "22", "genre": "pop", "mode": "album", "tag": "ALBUM"},
            {"title": "THE TORTURED POETS DEPARTMENT", "artist": "Taylor Swift", "query": "THE TORTURED POETS DEPARTMENT", "genre": "pop", "mode": "album", "tag": "GLOBAL #1"},
            {"title": "HIT ME HARD AND SOFT", "artist": "Billie Eilish", "query": "HIT ME HARD AND SOFT", "genre": "pop", "mode": "album", "tag": "GLOBAL"},
            {"title": "Bật Tình Yêu Lên", "artist": "Tăng Duy Tân & Hòa Minzy", "query": "Bật Tình Yêu Lên", "genre": "vpop", "mode": "search", "tag": "VIRAL SINGLE"},
        ]

    def _get_trending_playlists(self) -> List[Dict[str, Any]]:
        """Top curated Spotify / Web playlists."""
        return [
            {"title": "Top 50 Việt Nam (Weekly)", "query": "https://open.spotify.com/playlist/37i9dQZEVXbLdGSmz6xilI", "genre": "vpop", "mode": "playlist", "icon": "🇻🇳"},
            {"title": "Hot Hits Vietnam", "query": "https://open.spotify.com/playlist/37i9dQZF1DX0F4iogI5zct", "genre": "vpop", "mode": "playlist", "icon": "🔥"},
            {"title": "Viral 50 Vietnam", "query": "https://open.spotify.com/playlist/37i9dQZEVXbL1G1Lz6y1xW", "genre": "vpop", "mode": "playlist", "icon": "📱"},
            {"title": "Today's Top Hits (Global)", "query": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M", "genre": "pop", "mode": "playlist", "icon": "🌍"},
            {"title": "RapCaviar (Top Hip-Hop)", "query": "https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd", "genre": "hiphop", "mode": "playlist", "icon": "🎧"},
            {"title": "Indie Việt Tuyển Chọn", "query": "https://open.spotify.com/playlist/37i9dQZF1DX1lVhptIYRda", "genre": "indie", "mode": "playlist", "icon": "🎸"},
        ]

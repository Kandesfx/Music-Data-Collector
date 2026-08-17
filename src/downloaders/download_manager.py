"""
Music Data Collector - Download Manager Module v3 (Streaming Master Pipeline)
Orchestrates high-fidelity audio downloading with:
1. YTMusic Precision Matcher (Official clean audio filtering, duration matching)
2. In-process yt-dlp (320kbps MP3 transcoding)
3. LRCLIB Synced Lyrics (.lrc file generation for karaoke & USLT ID3 embedding)
4. Fallback resilience (yt-search -> spotDL) + HealthChecker + Session checkpointing.
"""

import sys
import time
import uuid
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable

import yt_dlp

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import settings
from src.storage.file_manager import FileManager
from src.storage.db_manager import DBManager
from src.processors.post_processor import PostProcessor
from src.processors.audio_feature_extractor import AudioFeatureExtractor
from src.downloaders.ytmusic_matcher import YTMusicMatcher
from src.collectors.lyrics_collector import LyricsCollector
from src.utils.fingerprint_generator import FingerprintGenerator
from src.utils.cookie_checker import CookieHealthChecker
from src.utils.health_checker import HealthChecker
from src.utils.session_manager import SessionManager
from src.utils.proxy_manager import ProxyManager
from src.utils.lock_manager import lock_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DownloadManager:
    """High-fidelity audio download manager with precision matching and lyrics extraction."""

    def __init__(
        self,
        db_manager: Optional[DBManager] = None,
        file_manager: Optional[FileManager] = None,
        session_manager: Optional[SessionManager] = None,
        health_checker: Optional[HealthChecker] = None,
        proxy_manager: Optional[ProxyManager] = None,
        on_cookie_expired: Optional[Callable[[str, str], None]] = None,
    ):
        self.db = db_manager or DBManager()
        self.fm = file_manager or FileManager()
        self.session_manager = session_manager or SessionManager()
        self.health_checker = health_checker or HealthChecker()
        self.proxy_manager = proxy_manager or ProxyManager()
        self.matcher = YTMusicMatcher()
        self.on_cookie_expired = on_cookie_expired

        self.browser_cookies = settings.COOKIES_FROM_BROWSER
        self.cookies_path = settings.YOUTUBE_COOKIES_PATH
        self.bitrate = settings.SPOTDL_BITRATE
        self.threads = settings.SPOTDL_THREADS

    def download_track(
        self,
        track: Dict[str, Any],
        session_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Download a single track using Precision YTMusic -> Fallback yt-dlp -> Fallback spotDL.
        Fetches synced lyrics (.lrc) and embeds ID3v2.3 tags with HD cover art.
        
        Returns:
            (success: bool, final_path: Optional[str], method: Optional[str])
        """
        spotify_id = track.get("spotify_id")
        title = track.get("name", "")
        artist = track.get("artist_name", "")
        album = track.get("album_name", "")
        duration_ms = track.get("duration_ms")
        spotify_url = track.get("spotify_url") or f"https://open.spotify.com/track/{spotify_id}"

        target_path = self.fm.get_audio_path(artist, spotify_id, title)

        # ─── 0. Check if already downloaded & valid ────────────────
        if self.fm.file_exists(target_path):
            is_valid, _ = PostProcessor.validate_audio_file(target_path)
            if is_valid:
                try:
                    rel_path = str(target_path.resolve().relative_to(settings.BASE_DIR.resolve())).replace("\\", "/")
                except Exception:
                    rel_path = str(target_path).replace("\\", "/")
                self.db.update_track_download_status(
                    spotify_id=spotify_id,
                    status="completed",
                    local_path=rel_path,
                    file_size_bytes=target_path.stat().st_size,
                    download_method="cached",
                )
                if session_id:
                    self.session_manager.checkpoint(
                        session_id=session_id,
                        spotify_id=spotify_id,
                        status="completed",
                        method="cached",
                        file_path=rel_path,
                    )
                self.health_checker.record(True)
                return True, str(target_path), "cached"

        # Acquire atomic per-track lock to prevent concurrent collisions on the same audio file
        worker_id = f"worker_{session_id or 'single'}_{uuid.uuid4().hex[:4]}"
        if not lock_manager.acquire_track_download_lock(spotify_id, owner=worker_id, ttl_seconds=180):
            logger.warning(f"🔒 Track {artist} - {title} ({spotify_id}) is currently being processed by another worker. Skipping collision.")
            return False, None, "Track is currently locked by another worker."

        # Unique isolated temporary directory
        temp_dir = settings.DATA_DIR / "temp" / f"{spotify_id}_{uuid.uuid4().hex[:6]}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            return self._execute_track_download(
                track=track,
                target_path=target_path,
                temp_dir=temp_dir,
                session_id=session_id,
            )
        finally:
            lock_manager.release_track_download_lock(spotify_id, owner=worker_id)

    def _execute_track_download(
        self,
        track: Dict[str, Any],
        target_path: Path,
        temp_dir: Path,
        session_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Internal execution of track download within secured lock boundary."""
        spotify_id = track.get("spotify_id")
        title = track.get("name", "")
        artist = track.get("artist_name", "")
        album = track.get("album_name", "")
        duration_ms = track.get("duration_ms")
        spotify_url = track.get("spotify_url") or f"https://open.spotify.com/track/{spotify_id}"

        downloaded_file: Optional[Path] = None
        method_used: Optional[str] = None
        error_message: Optional[str] = None
        current_proxy = self.proxy_manager.get_proxy()
        expected_sec = (duration_ms / 1000.0) if duration_ms else None

        # ─── 1. Primary Engine: YTMusic Precision Matcher (Multi-Candidate) ──
        logger.info(f"Searching official master audio for: {artist} - {title}...")
        candidates = self.matcher.find_candidates_ranked(
            artist=artist,
            title=title,
            duration_ms=duration_ms,
            max_candidates=3,
        )

        for cand in candidates:
            yt_url = cand.get("youtube_url")
            score = cand.get("score", 0)
            logger.info(f"Evaluating candidate ({score:.0f}%): {cand.get('title')} ({cand.get('duration')}) -> Downloading...")
            ytdlp_ok, ytdlp_file, ytdlp_err = self._download_ytdlp(
                target_url_or_query=yt_url,
                output_dir=temp_dir,
                proxy=current_proxy,
            )
            if ytdlp_ok and ytdlp_file and ytdlp_file.exists():
                # Sanity check candidate audio with Post-Download Duration & Header Guard
                is_valid, val_err = PostProcessor.validate_audio_file(
                    ytdlp_file,
                    expected_duration_sec=expected_sec,
                    max_duration_delta_sec=18.0,
                )
                if is_valid:
                    downloaded_file = ytdlp_file
                    method_used = "ytmusic_precision"
                    break
                else:
                    logger.warning(f"⚠️ Candidate {cand.get('title')} failed post-download guard ({val_err}). Trying next candidate...")
                    try:
                        ytdlp_file.unlink(missing_ok=True)
                    except Exception:
                        pass

        # ─── 2. Secondary Engine: General yt-dlp Search ──────────
        if not downloaded_file:
            logger.info(f"YTMusic precision candidates unavailable/rejected. Trying general yt-dlp search: {artist} - {title}...")
            search_query = f"{artist} - {title}"
            ytdlp_ok, ytdlp_file, ytdlp_err = self._download_ytdlp(
                target_url_or_query=search_query,
                output_dir=temp_dir,
                proxy=current_proxy,
            )
            if ytdlp_ok and ytdlp_file and ytdlp_file.exists():
                is_valid, _ = PostProcessor.validate_audio_file(ytdlp_file, expected_duration_sec=expected_sec)
                if is_valid:
                    downloaded_file = ytdlp_file
                    method_used = "ytdlp_search"

        # ─── 3. Tertiary Engine: spotDL Fallback ───────────
        if not downloaded_file:
            logger.warning("yt-dlp search failed/rejected. Falling back to spotDL...")
            spotdl_ok, spotdl_file, spotdl_err = self._download_spotdl(
                spotify_url=spotify_url,
                output_dir=temp_dir,
                proxy=current_proxy,
            )
            if spotdl_ok and spotdl_file and spotdl_file.exists():
                downloaded_file = spotdl_file
                method_used = "spotdl"
            else:
                error_message = f"yt-dlp: {ytdlp_err} | spotDL: {spotdl_err}"

        # ─── 4. Validate, Tag, Extract Lyrics & Finalize ──────────
        if downloaded_file and downloaded_file.exists():
            # Fetch lyrics from LRCLIB
            logger.info(f"Fetching synced & plain lyrics for: {artist} - {title}...")
            lyrics_data = LyricsCollector.fetch_lyrics(
                track_name=title,
                artist_name=artist,
                album_name=album,
                duration_ms=duration_ms,
            )

            plain_lyrics = lyrics_data.get("plain_lyrics") if lyrics_data else None
            synced_lyrics = lyrics_data.get("synced_lyrics") if lyrics_data else None

            # Auto-resolve cover art if missing
            if not track.get("image_url"):
                try:
                    import urllib.request, urllib.parse, json
                    clean_t = title.split("(")[0].split("-")[0].strip()
                    clean_a = artist.split(",")[0].strip()
                    q = urllib.parse.quote(f"{clean_a} {clean_t}".strip())
                    req = urllib.request.Request(f"https://itunes.apple.com/search?term={q}&entity=song&limit=1", headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=5) as res:
                        data = json.loads(res.read().decode("utf-8"))
                        if data.get("results"):
                            art = data["results"][0].get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")
                            if art:
                                track["image_url"] = art
                                self.db.db.tracks.update_one({"spotify_id": spotify_id}, {"$set": {"image_url": art}})
                except Exception:
                    pass

            # Embed ID3 tags (including lyrics and cover art HD)
            PostProcessor.fix_id3_tags(downloaded_file, track, lyrics_text=plain_lyrics)

            # Validate audio integrity
            is_valid, val_err = PostProcessor.validate_audio_file(downloaded_file)
            if is_valid:
                final_path = self.fm.move_file(downloaded_file, target_path)
                file_size = final_path.stat().st_size

                try:
                    rel_path = str(final_path.resolve().relative_to(settings.BASE_DIR.resolve())).replace("\\", "/")
                except Exception:
                    rel_path = str(final_path).replace("\\", "/")

                # Save Synced Lyrics (.lrc) alongside the MP3 file
                rel_lrc_path = None
                if synced_lyrics:
                    lrc_path = PostProcessor.save_synced_lyrics(final_path, synced_lyrics)
                    if lrc_path:
                        try:
                            rel_lrc_path = str(lrc_path.resolve().relative_to(settings.BASE_DIR.resolve())).replace("\\", "/")
                        except Exception:
                            rel_lrc_path = str(lrc_path).replace("\\", "/")

                # Update database
                self.db.update_track_download_status(
                    spotify_id=spotify_id,
                    status="completed",
                    local_path=rel_path,
                    file_size_bytes=file_size,
                    download_method=method_used,
                    lyrics_plain=plain_lyrics,
                    lyrics_synced=synced_lyrics,
                    lrc_path=rel_lrc_path,
                )

                # Real-time AI Audio Feature & Waveform Extraction
                try:
                    features = AudioFeatureExtractor.analyze_track(final_path, spotify_id=spotify_id)
                    if features.get("success"):
                        self.db.db["tracks"].update_one(
                            {"spotify_id": spotify_id},
                            {"$set": {"audio_features": features}}
                        )
                except Exception as ex_feat:
                    logger.debug(f"Audio feature extraction skipped for {spotify_id}: {ex_feat}")

                if session_id:
                    self.session_manager.checkpoint(
                        session_id=session_id,
                        spotify_id=spotify_id,
                        status="completed",
                        method=method_used,
                        file_path=rel_path,
                    )

                self.health_checker.record(True)
                if current_proxy:
                    self.proxy_manager.report_success(current_proxy)

                logger.info(f"✅ Successfully downloaded & verified: {final_path.name} ({method_used}) [Lyrics: {'Synced .lrc' if synced_lyrics else ('Plain' if plain_lyrics else 'None')}]")
                self._cleanup_temp(temp_dir)
                return True, str(final_path), method_used
            else:
                error_message = f"Validation failed: {val_err}"

        # ─── 5. Failure Handling ─────────────────────────────────
        if current_proxy:
            self.proxy_manager.report_failure(current_proxy)

        logger.error(f"Download failed for {artist} - {title}: {error_message}")
        if error_message:
            cookie_indicators = [
                "Sign in to confirm you’re not a bot",
                "cookies for the authentication",
                "LOGIN_REQUIRED",
                "HTTP Error 401",
                "login_required",
                "Sign in to confirm your age",
            ]
            if any(ci in error_message for ci in cookie_indicators):
                # Verify whether the cookie is ACTUALLY expired or if it was just an isolated video-level / IP restriction
                try:
                    cookie_health = CookieHealthChecker.check_health(probe_network=True)
                    if not cookie_health.get("valid", False):
                        logger.error(f"🚨 Xác nhận Cookie đã hết hạn thật sự: {cookie_health.get('message')}")
                        if hasattr(self, "on_cookie_expired") and self.on_cookie_expired:
                            self.on_cookie_expired("youtube", error_message)
                    else:
                        logger.info(
                            f"🟢 Kiểm tra nhanh: Cookie YouTube vẫn sống ({cookie_health.get('latency_ms')}ms, {cookie_health.get('cookie_count')} keys). "
                            f"Lỗi vừa rồi chỉ là giới hạn tần suất/bản quyền riêng của video này. Tiếp tục tải các bài tiếp theo."
                        )
                except Exception as ex:
                    logger.debug(f"Cookie health verification note: {ex}")

        self.db.update_track_download_status(
            spotify_id=spotify_id,
            status="failed",
            error=error_message,
        )
        if session_id:
            self.session_manager.checkpoint(
                session_id=session_id,
                spotify_id=spotify_id,
                status="failed",
                method=None,
                error=error_message,
            )

        self.health_checker.record(False)
        self._cleanup_temp(temp_dir)
        return False, None, None

    def download_direct_url(
        self,
        url: str,
        custom_title: Optional[str] = None,
        custom_artist: Optional[str] = None,
        genre: Optional[str] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Download any supported direct URL (YouTube, SoundCloud, TikTok, direct MP3 link)
        using yt-dlp, extract metadata, generate 320kbps MP3 and lyrics, and save to MongoDB.
        """
        logger.info(f"🌐 Ingesting audio from direct URL: {url}...")
        temp_dir = self.fm.create_temp_dir()
        current_proxy = self.proxy_manager.get_proxy() if self.proxy_manager.enabled else None

        # 1. Extract metadata via yt-dlp
        ydl_opts = {
            "extract_flat": False,
            "quiet": True,
            "no_warnings": True,
        }
        if current_proxy:
            ydl_opts["proxy"] = current_proxy

        info_dict = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
        except Exception as e:
            self._cleanup_temp(temp_dir)
            logger.error(f"Failed to extract info from direct URL {url}: {e}")
            return False, None, str(e)

        if not info_dict:
            self._cleanup_temp(temp_dir)
            return False, None, "Could not extract metadata from the provided URL."

        # Parse metadata
        raw_title = info_dict.get("title", "Unknown Track")
        uploader = info_dict.get("uploader") or info_dict.get("artist") or info_dict.get("channel", "Unknown Artist")
        duration_sec = info_dict.get("duration", 0)
        thumbnail = info_dict.get("thumbnail", "")
        webpage_url = info_dict.get("webpage_url", url)

        # Parse artist and title if formatted as "Artist - Title"
        title = custom_title or raw_title
        artist = custom_artist or uploader
        if " - " in raw_title and not custom_title and not custom_artist:
            parts = raw_title.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].strip()

        title = DataCleaner.clean_song_title(title)
        artist = DataCleaner.clean_text(artist)
        duration_ms = int(duration_sec * 1000)

        # Generate a unique slug ID for non-spotify source
        source_id = info_dict.get("id") or DataCleaner.slugify(title)
        spotify_id = f"ext_{source_id}"

        target_genre = genre or "pop"
        target_path = self.fm.get_target_audio_path(artist, title, spotify_id)

        # 2. Download audio stream at 320kbps
        ok, downloaded_file, dl_err = self._download_ytdlp(url, temp_dir, proxy=current_proxy)
        if not ok or not downloaded_file or not downloaded_file.exists():
            self._cleanup_temp(temp_dir)
            return False, None, f"Download failed: {dl_err}"

        # 3. Fetch lyrics from LRCLIB
        lyrics_data = LyricsCollector.fetch_lyrics(
            track_name=title,
            artist_name=artist,
            duration_ms=duration_ms,
        )
        plain_lyrics = lyrics_data.get("plain_lyrics") if lyrics_data else None
        synced_lyrics = lyrics_data.get("synced_lyrics") if lyrics_data else None

        track_dict = {
            "spotify_id": spotify_id,
            "name": title,
            "artist_name": artist,
            "artist_spotify_id": DataCleaner.slugify(artist),
            "artists": [{"id": DataCleaner.slugify(artist), "name": artist}],
            "album_name": f"{title} (Single)",
            "album_spotify_id": f"album_{spotify_id}",
            "duration_ms": duration_ms,
            "duration_formatted": f"{int(duration_ms / 60000)}:{int((duration_ms % 60000) / 1000):02d}",
            "image_url": thumbnail,
            "popularity": 80,
            "explicit": False,
            "track_number": 1,
            "genres": [target_genre],
            "genres_raw": [target_genre],
            "spotify_url": webpage_url,
            "download_status": "completed",
        }

        # 4. Embed ID3 tags & save .lrc
        PostProcessor.fix_id3_tags(downloaded_file, track_dict, lyrics_text=plain_lyrics)
        final_path = self.fm.move_file(downloaded_file, target_path)
        file_size = final_path.stat().st_size

        try:
            rel_path = str(final_path.resolve().relative_to(settings.BASE_DIR.resolve())).replace("\\", "/")
        except Exception:
            rel_path = str(final_path).replace("\\", "/")

        rel_lrc_path = None
        if synced_lyrics:
            lrc_path = PostProcessor.save_synced_lyrics(final_path, synced_lyrics)
            if lrc_path:
                try:
                    rel_lrc_path = str(lrc_path.resolve().relative_to(settings.BASE_DIR.resolve())).replace("\\", "/")
                except Exception:
                    rel_lrc_path = str(lrc_path).replace("\\", "/")

        # 5. Save to MongoDB
        artist_obj = {
            "spotify_id": DataCleaner.slugify(artist),
            "name": artist,
            "genres": [target_genre],
            "image_url": thumbnail,
            "popularity": 80,
            "followers": 0,
        }
        album_obj = {
            "spotify_id": f"album_{spotify_id}",
            "name": f"{title} (Single)",
            "artist_spotify_id": DataCleaner.slugify(artist),
            "artist_name": artist,
            "image_url": thumbnail,
            "total_tracks": 1,
        }

        self.db.upsert_artist(artist_obj)
        self.db.upsert_album(album_obj)
        self.db.upsert_genre(target_genre, target_genre.capitalize())
        self.db.upsert_track(track_dict)
        self.db.update_track_download_status(
            spotify_id=spotify_id,
            status="completed",
            local_path=rel_path,
            file_size_bytes=file_size,
            download_method="yt-dlp-direct",
            lyrics_plain=plain_lyrics,
            lyrics_synced=synced_lyrics,
            lrc_path=rel_lrc_path,
        )

        self._cleanup_temp(temp_dir)
        logger.info(f"✅ Successfully ingested direct URL track: {artist} - {title} ({final_path.name})")
        return True, track_dict, None

    def _get_active_cookie_file(self) -> Optional[str]:
        """Resolve active cookies.txt file across standard locations."""
        candidates = [
            self.cookies_path,
            settings.CONFIG_DIR / "cookies.txt",
            settings.DATA_DIR / "cookies.txt",
            settings.BASE_DIR / "config" / "cookies.txt",
            settings.BASE_DIR / "cookies.txt",
            Path("/opt/music-data-collector/config/cookies.txt"),
            Path("/opt/music-data-collector/data/cookies.txt"),
        ]
        for cand in candidates:
            if cand:
                p = Path(cand)
                if p.exists() and p.is_file() and p.stat().st_size > 10:
                    return str(p.resolve())
        return None

    def _download_spotdl(
        self,
        spotify_url: str,
        output_dir: Path,
        proxy: Optional[str] = None,
    ) -> Tuple[bool, Optional[Path], Optional[str]]:
        """Download track via spotDL CLI tool."""
        cmd = [
            sys.executable,
            "-m",
            "spotdl",
            "download",
            spotify_url,
            "--output",
            str(output_dir),
            "--format",
            "mp3",
            "--bitrate",
            self.bitrate,
            "--threads",
            str(self.threads),
            "--headless",
        ]

        active_cookie = self._get_active_cookie_file()
        if active_cookie:
            cmd.extend(["--cookie-file", active_cookie])

        if proxy:
            cmd.extend(["--proxy", proxy])

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            if res.returncode == 0:
                mp3_files = list(output_dir.glob("*.mp3"))
                if mp3_files:
                    return True, mp3_files[0], None
                return False, None, "spotDL succeeded but no MP3 file was found in output folder."
            else:
                return False, None, res.stderr.strip() or res.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, None, "spotDL timed out after 60 seconds."
        except Exception as e:
            return False, None, str(e)

    def _download_ytdlp(
        self,
        target_url_or_query: str,
        output_dir: Path,
        proxy: Optional[str] = None,
    ) -> Tuple[bool, Optional[Path], Optional[str]]:
        """Download track directly from YouTube/YTMusic using yt-dlp in-process at 320kbps with auto-fallback."""
        out_template = str(output_dir / "audio.%(ext)s")
        active_cookie = self._get_active_cookie_file()

        # Build fallback proxy sequence
        proxy_candidates = [proxy]
        if self.proxy_manager.enabled:
            alt_proxy = self.proxy_manager.get_proxy()
            if alt_proxy and alt_proxy not in proxy_candidates:
                proxy_candidates.append(alt_proxy)
            # Add WARP fallback if not already primary
            warp_proxy = "socks5://127.0.0.1:40000"
            if warp_proxy not in proxy_candidates:
                proxy_candidates.append(warp_proxy)
        # Direct attempt as last resort
        if None not in proxy_candidates:
            proxy_candidates.append(None)

        last_error = None
        for attempt_idx, current_proxy in enumerate(proxy_candidates[:3]):
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": out_template,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "320",
                    }
                ],
                "extractor_args": FingerprintGenerator.get_ytdlp_extractor_args(),
                "http_headers": FingerprintGenerator.get_ytdlp_http_headers(),
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "socket_timeout": 30,
            }

            if not target_url_or_query.startswith("http://") and not target_url_or_query.startswith("https://"):
                ydl_opts["default_search"] = "ytsearch1"

            if active_cookie:
                ydl_opts["cookiefile"] = active_cookie

            if current_proxy:
                ydl_opts["proxy"] = current_proxy

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([target_url_or_query])

                mp3_files = list(output_dir.glob("*.mp3"))
                if mp3_files:
                    return True, mp3_files[0], None
            except Exception as e:
                err_str = str(e)
                last_error = err_str
                if current_proxy:
                    self.proxy_manager.report_failure(current_proxy)

                # Check if network lost completely
                if any(kw in err_str.lower() for kw in ["connection refused", "name resolution", "network is unreachable"]):
                    self.db.log_activity(
                        username="system",
                        action="NETWORK_ERROR",
                        status="FAILED",
                        details=f"Mất kết nối mạng khi tải '{target_url_or_query[:35]}': {err_str}",
                    )

                # Auto rotate fingerprint on bot error
                if "sign in to confirm" in err_str.lower() or "bot" in err_str.lower():
                    FingerprintGenerator.set_active_profile("random")

                time.sleep(1)

        return False, None, last_error or "yt-dlp failed on all fallback attempts."

    def _cleanup_temp(self, temp_dir: Path):
        """Remove temporary directory."""
        try:
            if temp_dir.exists():
                shutil.rmtree(str(temp_dir))
        except Exception:
            pass

    # Aliases for compatibility
    _download_via_ytdlp = _download_ytdlp
    _download_via_spotdl = _download_spotdl

    def download_batch(
        self,
        tracks: List[Dict[str, Any]],
        delay_seconds: float = settings.DOWNLOAD_DELAY_SECONDS,
        batch_size: int = settings.BATCH_SIZE,
        cooldown_seconds: int = settings.BATCH_COOLDOWN_SECONDS,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        should_pause_check: Optional[Callable[[], bool]] = None,
        should_stop_check: Optional[Callable[[], bool]] = None,
        session_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Download multiple tracks with session checkpointing, auto-cool-off, and real-time callbacks.
        """
        completed_ids = self.session_manager.get_completed_spotify_ids()
        pending_tracks = [t for t in tracks if t.get("spotify_id") not in completed_ids]

        total_pending = len(pending_tracks)
        if session_id is None:
            session_id = self.session_manager.start_session(total_pending)

        logger.info(
            f"Starting batch session #{session_id} for {total_pending} tracks "
            f"(batch: {batch_size}, delay: {delay_seconds}s, cooldown: {cooldown_seconds}s)..."
        )

        successful_count = 0
        failed_count = 0
        consecutive_failures = 0

        for idx, track in enumerate(pending_tracks, 1):
            if should_stop_check and should_stop_check():
                logger.info("Batch download interrupted by stop signal.")
                break

            while should_pause_check and should_pause_check():
                logger.info("Batch download is paused. Waiting 2s...")
                time.sleep(2)
                if should_stop_check and should_stop_check():
                    break

            if self.health_checker.should_pause():
                wait_time = self.health_checker.get_pause_duration()
                logger.warning(f"Health threshold triggered! Backing off for {wait_time}s...")
                time.sleep(wait_time)

            spotify_id = track.get("spotify_id")
            title = track.get("name", "Unknown")
            artist = track.get("artist_name", "Unknown")

            # 1. Notify progress callback before starting download
            if progress_callback:
                progress_callback({
                    "session_id": session_id,
                    "index": idx,
                    "total": total_pending,
                    "track": track,
                    "track_name": f"{artist} - {title}",
                    "stage": "starting",
                    "status": "in_progress",
                    "method": None,
                    "success_count": successful_count,
                    "failed_count": failed_count,
                    "health": self.health_checker.get_status(),
                })

            ok, path, method = self.download_track(track, session_id=session_id)

            if ok:
                successful_count += 1
                consecutive_failures = 0
            else:
                failed_count += 1
                consecutive_failures += 1

            # 2. Notify progress callback after download completion
            if progress_callback:
                progress_callback({
                    "session_id": session_id,
                    "index": idx,
                    "total": total_pending,
                    "track": track,
                    "track_name": f"{artist} - {title}",
                    "stage": "finished",
                    "status": "success" if ok else "failed",
                    "method": method,
                    "success_count": successful_count,
                    "failed_count": failed_count,
                    "health": self.health_checker.get_status(),
                })

            if idx < total_pending:
                if idx % batch_size == 0:
                    logger.info(f"Batch limit reached ({batch_size} tracks). Cooldown for {cooldown_seconds}s...")
                    time.sleep(cooldown_seconds)
                else:
                    time.sleep(delay_seconds)

        final_status = "completed" if failed_count == 0 else "completed_with_errors"
        self.session_manager.end_session(session_id, final_status)

        return {
            "session_id": session_id,
            "total": total_pending,
            "successful": successful_count,
            "failed": failed_count,
            "status": final_status,
        }

    def download_batch_parallel(
        self,
        limit: Optional[int] = None,
        max_workers: int = 4,
        specific_ids: Optional[List[str]] = None,
        retry_failed: bool = False,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        should_stop_check: Optional[Callable[[], bool]] = None,
        should_pause_check: Optional[Callable[[], bool]] = None,
        session_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Download tracks in parallel across max_workers concurrent worker threads.
        Accelerates batch downloads from minutes to seconds using multi-core processing.
        """
        if specific_ids:
            pending_tracks = []
            for sid in specific_ids:
                t = self.db.get_track(sid)
                if t:
                    pending_tracks.append(t)
        elif retry_failed:
            pending_tracks = self.db.get_failed_tracks(limit=limit)
        else:
            pending_tracks = self.db.get_pending_tracks(limit=limit)

        total_pending = len(pending_tracks)
        if total_pending == 0:
            return {"session_id": session_id, "total": 0, "successful": 0, "failed": 0, "status": "no_pending"}

        if session_id is None:
            session_id = self.session_manager.start_session(total_pending)

        workers = max(1, min(8, int(max_workers)))
        logger.info(f"⚡ Launching Multi-Worker Accelerator ({workers} concurrent workers) for {total_pending} tracks...")

        completed_count = 0
        successful_count = 0
        failed_count = 0
        results_lock = threading.Lock()

        def _worker_task(item_idx: int, track_item: Dict[str, Any]):
            nonlocal completed_count, successful_count, failed_count
            if should_stop_check and should_stop_check():
                return False, None, "stopped"

            while should_pause_check and should_pause_check():
                time.sleep(1)
                if should_stop_check and should_stop_check():
                    return False, None, "stopped"

            ok, path, method = self.download_track(track_item, session_id=session_id)

            with results_lock:
                completed_count += 1
                if ok:
                    successful_count += 1
                else:
                    failed_count += 1

                if progress_callback:
                    progress_callback({
                        "session_id": session_id,
                        "index": completed_count,
                        "total": total_pending,
                        "track": track_item,
                        "track_name": f"{track_item.get('artist_name')} - {track_item.get('name')}",
                        "stage": "finished",
                        "status": "success" if ok else "failed",
                        "method": method,
                        "success_count": successful_count,
                        "failed_count": failed_count,
                        "health": self.health_checker.get_status(),
                    })

            return ok, path, method

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_worker_task, idx, t) for idx, t in enumerate(pending_tracks, 1)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as ex:
                    logger.debug(f"Worker task error: {ex}")

        final_status = "completed" if failed_count == 0 else "completed_with_errors"
        self.session_manager.end_session(session_id, final_status)

        return {
            "session_id": session_id,
            "total": total_pending,
            "successful": successful_count,
            "failed": failed_count,
            "status": final_status,
            "workers": workers,
        }

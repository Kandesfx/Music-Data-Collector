"""
Music Data Collector - Real-time Web Dashboard Server
Provides Flask + SocketIO control center to monitor and command the pipeline.
"""

import os
import sys
import threading
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file, Response
from flask_socketio import SocketIO, emit

from config import settings
from src.collectors.spotify_collector import SpotifyCollector
from src.downloaders.download_manager import DownloadManager
from src.processors.deduplicator import Deduplicator
from src.storage.db_manager import DBManager
from src.storage.file_manager import FileManager
from src.storage.export_manager import ExportManager
from src.storage.auth_manager import AuthManager
from src.collectors.trend_manager import TrendManager
from src.utils.health_checker import HealthChecker
from src.utils.session_manager import SessionManager
from src.utils.proxy_manager import ProxyManager
from src.utils.cookie_checker import CookieHealthChecker
from src.utils.warp_controller import WarpController
from src.utils.tailscale_controller import TailscaleController
from src.utils.fingerprint_generator import FingerprintGenerator
from src.utils.lock_manager import lock_manager
from src.utils.logger import get_logger

logger = get_logger("dashboard")

app = Flask(__name__)
app.config["SECRET_KEY"] = settings.DASHBOARD_SECRET_KEY if hasattr(settings, "DASHBOARD_SECRET_KEY") else "music-collector-secret-2026-datn"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


@app.context_processor
def inject_asset_version():
    return {"asset_version": int(time.time())}


@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


class PipelineController:
    """Controls the background pipeline and broadcasts telemetry via WebSockets."""

    def __init__(self):
        self.db = DBManager()
        self.auth = AuthManager(self.db)
        self.fm = FileManager()
        self.sm = SessionManager()
        self.pm = ProxyManager(db_manager=self.db)
        self.health = HealthChecker()
        self.dm = DownloadManager(
            db_manager=self.db,
            file_manager=self.fm,
            session_manager=self.sm,
            health_checker=self.health,
            proxy_manager=self.pm,
            on_cookie_expired=self.handle_cookie_expired,
        )
        FingerprintGenerator.set_db_manager(self.db)
        lock_manager.set_db_manager(self.db)

        # Multi-Job Concurrent Registry
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
        self._jobs_lock = threading.RLock()

        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        self.active_task_name = "Idle"
        self.current_track: Optional[Dict[str, Any]] = None

    def handle_cookie_expired(self, service: str, error_detail: str):
        """Triggered immediately when a download fails due to expired or revoked cookies."""
        msg = f"🚨 CẢNH BÁO: Cookie {service.upper()} đã hết hạn hoặc bị đăng xuất! Hãy cập nhật cookie mới trong cài đặt."
        self.log(msg, level="error")
        socketio.emit("cookie_expired_alert", {
            "service": service,
            "error": error_detail,
            "message": msg,
            "timestamp": time.strftime("%H:%M:%S")
        })

    def log(self, message: str, level: str = "info"):
        """Broadcast log message to connected UI clients."""
        logger.info(message)
        socketio.emit("log_entry", {"message": message, "level": level, "timestamp": time.strftime("%H:%M:%S")})

    def get_active_jobs_list(self) -> List[Dict[str, Any]]:
        """Return serialized list of all currently active concurrent jobs."""
        with self._jobs_lock:
            result = []
            for jid, job in self.active_jobs.items():
                result.append({
                    "job_id": jid,
                    "job_type": job.get("job_type"),
                    "task_name": job.get("task_name"),
                    "operator": job.get("operator"),
                    "status": job.get("status"),
                    "created_at": job.get("created_at"),
                    "started_at": job.get("started_at"),
                    "progress": job.get("progress", {}),
                })
            return result

    def broadcast_jobs_state(self):
        """Broadcast active jobs to all connected WebSocket clients."""
        jobs_list = self.get_active_jobs_list()
        self.is_running = len(jobs_list) > 0
        if not self.is_running:
            self.active_task_name = "Idle"
        else:
            self.active_task_name = f"Đang chạy ({len(jobs_list)} tác vụ song song)"

        socketio.emit("active_jobs_update", {
            "jobs": jobs_list,
            "total_active": len(jobs_list),
            "is_running": self.is_running,
            "active_task_name": self.active_task_name,
        })
        self.broadcast_stats()

    def start_crawl_task(
        self,
        mode: str = "curated",
        query: str = "",
        genre: Optional[str] = None,
        limit_per_playlist: int = 50,
        operator_name: str = "admin",
    ) -> Dict[str, Any]:
        """Run metadata crawling in an isolated concurrent worker job."""
        job_id = f"job_crawl_{operator_name}_{int(time.time()*1000)}"
        task_name = f"Crawl [{mode.upper()}]: {query or 'Curated'} ({genre or 'auto'})"

        stop_event = threading.Event()
        pause_event = threading.Event()

        job_info = {
            "job_id": job_id,
            "job_type": "crawl",
            "task_name": task_name,
            "operator": operator_name,
            "status": "running",
            "created_at": datetime.utcnow().isoformat(),
            "started_at": datetime.utcnow().isoformat(),
            "progress": {
                "current": 0,
                "total": limit_per_playlist,
                "percent": 0,
                "current_item": "Khởi động...",
                "success_count": 0,
                "failed_count": 0,
            },
            "stop_event": stop_event,
            "pause_event": pause_event,
        }

        with self._jobs_lock:
            self.active_jobs[job_id] = job_info

        self.log(f"🚀 [Job {job_id[:12]}] Khởi chạy tác vụ Cào Metadata bởi @{operator_name}: '{task_name}'...", level="info")
        self.broadcast_jobs_state()

        def _crawl_worker():
            try:
                collector = SpotifyCollector()
                all_raw_tracks = []

                if mode == "curated" and not query:
                    playlists_path = settings.CONFIG_DIR / "playlists.json"
                    if not playlists_path.exists():
                        playlists_path = settings.BASE_DIR / "config" / "playlists.json"

                    with open(playlists_path, "r", encoding="utf-8") as f:
                        target_playlists = json.load(f).get("playlists", [])

                    self.log(f"📋 [Job {job_id[:12]}] Starting curated crawl across {len(target_playlists)} playlists...")

                    for idx, pl in enumerate(target_playlists):
                        if stop_event.is_set():
                            self.log(f"🛑 [Job {job_id[:12]}] Cào metadata đã bị dừng bởi người dùng.", level="warning")
                            break

                        while pause_event.is_set() and not stop_event.is_set():
                            time.sleep(0.5)

                        pl_name = pl.get("name")
                        pl_url = pl.get("url")
                        pl_genre = pl.get("genre", "pop")

                        job_info["progress"]["current"] = idx + 1
                        job_info["progress"]["total"] = len(target_playlists)
                        job_info["progress"]["percent"] = int((idx + 1) / max(len(target_playlists), 1) * 100)
                        job_info["progress"]["current_item"] = f"Playlist: {pl_name}"
                        socketio.emit("job_progress", {"job_id": job_id, "progress": job_info["progress"]})

                        try:
                            tracks = collector.collect_playlist_tracks(pl_url, max_tracks=limit_per_playlist, default_genre=pl_genre)
                            for t in tracks:
                                if pl_genre and pl_genre not in t.get("genres", []):
                                    t["genres"].append(pl_genre)
                            all_raw_tracks.extend(tracks)
                            self.db.upsert_genre(pl_genre, pl_name)
                        except Exception as e:
                            self.log(f"Error in playlist {pl_name}: {e}", level="error")

                else:
                    target_query = query.strip()
                    job_info["progress"]["current_item"] = f"Tìm kiếm: {target_query}"
                    socketio.emit("job_progress", {"job_id": job_id, "progress": job_info["progress"]})

                    tracks = collector.collect_custom(mode=mode, query=target_query, max_tracks=limit_per_playlist, default_genre=genre)
                    all_raw_tracks.extend(tracks)
                    if genre:
                        self.db.upsert_genre(genre, genre.upper())

                # Multi-Tier Deduplication against existing DB
                existing_db_tracks = self.db.get_all_tracks()
                unique_new, updated_existing, skipped_dups = Deduplicator.dedup_tracks(
                    tracks=all_raw_tracks,
                    existing_db_tracks=existing_db_tracks,
                )

                all_active_tracks = unique_new + updated_existing
                for t in all_active_tracks:
                    if not t.get("added_by"):
                        t["added_by"] = operator_name
                    if not t.get("ingest_type"):
                        t["ingest_type"] = "metadata_only"

                artists_map = collector.collect_artists_info([t.get("artist_spotify_id") for t in all_active_tracks], tracks=all_active_tracks)
                albums_map = collector.collect_albums_info([t.get("album_spotify_id") for t in all_active_tracks], tracks=all_active_tracks)

                if artists_map:
                    self.db.bulk_upsert_artists(list(artists_map.values()))
                if albums_map:
                    self.db.bulk_upsert_albums(list(albums_map.values()))
                if unique_new:
                    self.db.bulk_upsert_tracks(unique_new)
                if updated_existing:
                    self.db.bulk_upsert_tracks(updated_existing)

                auth_mgr.record_user_action(
                    username=operator_name,
                    action_type="crawl_metadata",
                    count=len(unique_new),
                    details=f"Crawl [{mode.upper()}]: +{len(unique_new)} tracks ('{query or 'Curated'}')",
                )
                self.db.log_activity(
                    username=operator_name,
                    action="CRAWL_METADATA",
                    status="SUCCESS",
                    details=f"Cào metadata [{mode.upper()}]: +{len(unique_new)} bài mới, {len(updated_existing)} cập nhật",
                    target=f"{len(all_active_tracks)} tracks",
                )

                job_info["status"] = "completed"
                job_info["progress"]["percent"] = 100
                job_info["progress"]["current_item"] = f"Hoàn tất (+{len(unique_new)} mới, {len(updated_existing)} cập nhật)"
                self.log(f"✅ [Job {job_id[:12]}] Metadata crawl completed! (+{len(unique_new)} bài mới by @{operator_name})", level="success")
            except Exception as ex:
                job_info["status"] = "failed"
                job_info["error"] = str(ex)
                self.db.log_activity(
                    username=operator_name,
                    action="CRAWL_METADATA",
                    status="FAILED",
                    details=f"Cào metadata thất bại: {ex}",
                    target=mode,
                )
                self.log(f"❌ [Job {job_id[:12]}] Crawl failed: {ex}", level="error")
            finally:
                time.sleep(2)
                with self._jobs_lock:
                    if job_id in self.active_jobs:
                        del self.active_jobs[job_id]
                self.broadcast_jobs_state()

        worker_t = threading.Thread(target=_crawl_worker, daemon=True)
        job_info["thread"] = worker_t
        worker_t.start()
        return {"success": True, "job_id": job_id, "task_name": task_name}

    def start_download_task(
        self,
        limit: int = 50,
        delay: float = 4.0,
        retry_failed: bool = False,
        operator_name: str = "admin",
        specific_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run audio download in an isolated concurrent worker job with atomic work partitioning."""
        job_id = f"job_dl_{operator_name}_{int(time.time()*1000)}"

        # 1. Atomically claim unique batch of tracks exclusively for this job
        claimed_tracks = self.db.claim_tracks_for_job(
            job_id=job_id,
            operator=operator_name,
            limit=limit,
            status="failed" if retry_failed else "pending",
            specific_ids=specific_ids,
        )

        if not claimed_tracks:
            msg = "Không có bài hát nào phù hợp trong hàng đợi hoặc tất cả bài đang được xử lý bởi các tiến trình khác."
            self.log(msg, level="warning")
            return {"success": False, "error": msg}

        task_name = f"Batch Download ({len(claimed_tracks)} bài)"
        stop_event = threading.Event()
        pause_event = threading.Event()

        job_info = {
            "job_id": job_id,
            "job_type": "download",
            "task_name": task_name,
            "operator": operator_name,
            "status": "running",
            "created_at": datetime.utcnow().isoformat(),
            "started_at": datetime.utcnow().isoformat(),
            "progress": {
                "current": 0,
                "total": len(claimed_tracks),
                "percent": 0,
                "current_item": "Khởi tạo kết nối...",
                "success_count": 0,
                "failed_count": 0,
            },
            "stop_event": stop_event,
            "pause_event": pause_event,
        }

        with self._jobs_lock:
            self.active_jobs[job_id] = job_info

        self.log(f"🎧 [Job {job_id[:12]}] Bắt đầu tải {len(claimed_tracks)} bài hát song song (Operator: @{operator_name})...", level="info")
        self.broadcast_jobs_state()

        def _download_worker():
            try:
                def _progress_cb(info):
                    t = info.get("track", {})
                    curr_idx = info.get("index") or info.get("current_index", 1)
                    total = info.get("total", len(claimed_tracks))
                    pct = int(curr_idx / max(total, 1) * 100)
                    t_title = t.get("name", "Unknown")
                    t_artist = t.get("artist_name", "Unknown")
                    stage = info.get("stage", "finished")
                    status = info.get("status", "in_progress")

                    job_info["progress"]["current"] = curr_idx
                    job_info["progress"]["total"] = total
                    job_info["progress"]["percent"] = pct
                    job_info["progress"]["current_item"] = f"{t_artist} - {t_title}"
                    job_info["progress"]["success_count"] = info.get("success_count", 0)
                    job_info["progress"]["failed_count"] = info.get("failed_count", 0)

                    socketio.emit("job_progress", {
                        "job_id": job_id,
                        "progress": job_info["progress"],
                    })

                    if stage == "starting":
                        self.log(f"🎵 [Job {job_id[:12]}] [{curr_idx}/{total}] Đang tải: {t_artist} - {t_title}...")
                    elif stage == "finished":
                        if status == "success":
                            self.log(f"✅ [Job {job_id[:12]}] [{curr_idx}/{total}] Tải xong: {t_artist} - {t_title}", level="success")
                        else:
                            self.log(f"❌ [Job {job_id[:12]}] [{curr_idx}/{total}] Lỗi tải: {t_artist} - {t_title}", level="error")
                        self.broadcast_stats()

                res = self.dm.download_batch(
                    tracks=claimed_tracks,
                    delay_seconds=delay,
                    progress_callback=_progress_cb,
                    should_pause_check=lambda: pause_event.is_set(),
                    should_stop_check=lambda: stop_event.is_set(),
                    session_id=int(time.time()),
                )

                s_cnt = res.get("successful", res.get("success", 0))
                f_cnt = res.get("failed", 0)

                auth_mgr.record_user_action(
                    username=operator_name,
                    action_type="download_audio",
                    count=s_cnt,
                    details=f"Downloaded {s_cnt} MP3 tracks (Job {job_id[:8]})",
                )
                self.db.log_activity(
                    username=operator_name,
                    action="DOWNLOAD_AUDIO",
                    status="SUCCESS" if s_cnt > 0 else "WARNING",
                    details=f"Tải batch audio song song ({job_id[:8]}): {s_cnt} thành công, {f_cnt} thất bại",
                    target=f"{len(claimed_tracks)} tracks",
                )

                job_info["status"] = "completed"
                job_info["progress"]["percent"] = 100
                self.log(f"🏁 [Job {job_id[:12]}] Hoàn tất tải: {s_cnt} thành công, {f_cnt} thất bại (by @{operator_name}).", level="success")
            except Exception as ex:
                job_info["status"] = "failed"
                job_info["error"] = str(ex)
                self.db.log_activity(
                    username=operator_name,
                    action="DOWNLOAD_AUDIO",
                    status="FAILED",
                    details=f"Tải batch audio lỗi: {ex}",
                    target=job_id,
                )
                self.log(f"❌ [Job {job_id[:12]}] Download worker error: {ex}", level="error")
            finally:
                # Release claims on any tracks not downloaded
                self.db.release_job_claims(job_id)
                time.sleep(2)
                with self._jobs_lock:
                    if job_id in self.active_jobs:
                        del self.active_jobs[job_id]
                self.broadcast_jobs_state()

        worker_t = threading.Thread(target=_download_worker, daemon=True)
        job_info["thread"] = worker_t
        worker_t.start()
        return {"success": True, "job_id": job_id, "task_name": task_name, "claimed_count": len(claimed_tracks)}

    def pause_job(self, job_id: str, operator_name: str = "admin") -> bool:
        """Pause a specific running job."""
        with self._jobs_lock:
            job = self.active_jobs.get(job_id)
            if not job:
                return False
            pause_event = job.get("pause_event")
            if pause_event:
                pause_event.set()
                job["status"] = "paused"
                self.log(f"⏸️ [Job {job_id[:12]}] Tác vụ đã tạm dừng bởi @{operator_name}.", level="info")
                self.broadcast_jobs_state()
                return True
            return False

    def resume_job(self, job_id: str, operator_name: str = "admin") -> bool:
        """Resume a paused job."""
        with self._jobs_lock:
            job = self.active_jobs.get(job_id)
            if not job:
                return False
            pause_event = job.get("pause_event")
            if pause_event:
                pause_event.clear()
                job["status"] = "running"
                self.log(f"▶️ [Job {job_id[:12]}] Tác vụ được tiếp tục bởi @{operator_name}.", level="info")
                self.broadcast_jobs_state()
                return True
            return False

    def stop_job(self, job_id: str, operator_name: str = "admin") -> bool:
        """Stop and terminate a specific job."""
        with self._jobs_lock:
            job = self.active_jobs.get(job_id)
            if not job:
                return False
            stop_event = job.get("stop_event")
            if stop_event:
                stop_event.set()
                job["status"] = "stopped"
                self.db.release_job_claims(job_id)
                self.log(f"⏹️ [Job {job_id[:12]}] Tác vụ đã bị hủy bởi @{operator_name}.", level="warning")
                self.broadcast_jobs_state()
                return True
            return False

    def pause(self):
        """Toggle pause across all active jobs (Global switch)."""
        self.is_paused = not self.is_paused
        with self._jobs_lock:
            for jid, job in self.active_jobs.items():
                pe = job.get("pause_event")
                if pe:
                    if self.is_paused:
                        pe.set()
                        job["status"] = "paused"
                    else:
                        pe.clear()
                        job["status"] = "running"
        self.broadcast_jobs_state()

    def stop(self):
        """Stop all active jobs immediately."""
        self.should_stop = True
        with self._jobs_lock:
            for jid, job in self.active_jobs.items():
                se = job.get("stop_event")
                if se:
                    se.set()
                self.db.release_job_claims(jid)
            self.active_jobs.clear()
        lock_manager.release_lock("pipeline_global_lock")
        self.broadcast_jobs_state()

    def toggle_proxy(self, enable: bool):
        """Toggle proxy usage."""
        self.pm.toggle(enable)
        self.log(f"Proxy rotation {'enabled' if enable else 'disabled'}.")
        socketio.emit("proxy_status", self.pm.get_status())

    def broadcast_stats(self):
        """Send updated statistics across all collections."""
        stats = self.db.get_statistics()
        storage = self.fm.get_storage_stats()
        sessions = self.sm.get_session_stats()
        health = self.health.get_status()
        proxy = self.pm.get_status()

        socketio.emit(
            "stats_update",
            {
                "stats": stats,
                "storage": storage,
                "sessions": sessions,
                "health": health,
                "proxy": proxy,
                "task": self.active_task_name,
                "is_running": self.is_running,
                "is_paused": self.is_paused,
            },
        )


controller = PipelineController()
auth_mgr = AuthManager(db_manager=controller.db)


# ─── Auth & Page Routes ──────────────────────────────────────

@app.route("/")
def index():
    """Render main dashboard web page (Protected by Auth session)."""
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    return render_template("index.html", current_user=user)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = auth_mgr.authenticate_user(username, password)
        if user:
            session["user"] = user
            controller.log(f"User '{username}' logged into Studio.", level="info")
            return redirect(url_for("index"))
        return render_template("login.html", error="Sai tên đăng nhập hoặc mật khẩu!")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Handle member registration."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        if len(password) < 6:
            return render_template("register.html", error="Mật khẩu tối thiểu 6 ký tự!")
        user = auth_mgr.create_user(username=username, password=password, email=email, role="collector")
        if user:
            session["user"] = user
            controller.log(f"New member '{username}' registered and joined Studio.", level="success")
            return redirect(url_for("index"))
        return render_template("register.html", error="Tên đăng nhập đã tồn tại, vui lòng chọn tên khác!")
    return render_template("register.html")


@app.route("/logout")
def logout():
    """Clear session and log out."""
    user = session.pop("user", None)
    if user:
        controller.log(f"User '{user.get('username')}' logged out.", level="info")
    return redirect(url_for("login"))


# ─── Audio Streaming & Lyrics API (For Web ReactJS & Mobile Flutter) ──

@app.route("/api/stream/<spotify_id>")
def stream_audio(spotify_id):
    """
    Stream audio file supporting HTTP 206 Partial Content (Byte-Range requests)
    for seamless scrubbing and seeking on Web ReactJS and Mobile Flutter apps.
    """
    track = controller.db.get_track(spotify_id)
    if not track or not track.get("local_path"):
        return jsonify({"error": "Track not found or audio not downloaded yet"}), 404

    local_path = settings.BASE_DIR / track["local_path"]
    if not local_path.exists():
        matches = list(settings.AUDIO_DIR.glob(f"**/*{spotify_id}*.mp3"))
        if matches:
            local_path = matches[0]
        else:
            return jsonify({"error": "Audio file missing on disk"}), 404

    file_size = local_path.stat().st_size
    range_header = request.headers.get("Range", None)

    if not range_header:
        return send_file(local_path, mimetype="audio/mpeg")

    byte1, byte2 = 0, None
    m = re.search(r"(\d+)-(\d*)", range_header)
    if m:
        g = m.groups()
        if g[0]:
            byte1 = int(g[0])
        if g[1]:
            byte2 = int(g[1])

    length = file_size - byte1
    if byte2 is not None:
        length = byte2 - byte1 + 1

    with open(local_path, "rb") as f:
        f.seek(byte1)
        data = f.read(length)

    rv = Response(data, 206, mimetype="audio/mpeg", direct_passthrough=True)
    rv.headers.add("Content-Range", f"bytes {byte1}-{byte1 + length - 1}/{file_size}")
    rv.headers.add("Accept-Ranges", "bytes")
    rv.headers.add("Content-Length", str(length))
    return rv


@app.route("/api/lyrics/<spotify_id>")
def get_lyrics(spotify_id):
    """Serve plain & synced .lrc lyrics for Web & Flutter app."""
    track = controller.db.get_track(spotify_id)
    if not track:
        return jsonify({"error": "Track not found"}), 404

    synced = track.get("lyrics_synced")
    plain = track.get("lyrics_plain")

    if not synced and track.get("lrc_path"):
        lrc_file = settings.BASE_DIR / track["lrc_path"]
        if lrc_file.exists():
            try:
                with open(lrc_file, "r", encoding="utf-8") as f:
                    synced = f.read()
            except Exception:
                pass

    return jsonify({
        "spotify_id": spotify_id,
        "name": track.get("name"),
        "artist_name": track.get("artist_name"),
        "has_synced_lyrics": bool(synced),
        "synced_lyrics": synced,
        "plain_lyrics": plain,
    })


# ─── Database Catalog Management REST APIs ───────────────────

@app.route("/api/tracks", methods=["GET"])
def api_get_tracks():
    """Server-side paginated & filtered tracks query for Catalog Studio."""
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    search = request.args.get("search", "").strip()
    genre = request.args.get("genre", None)
    download_status = request.args.get("download_status", None)
    moderation_status = request.args.get("moderation_status", None)
    added_by = request.args.get("added_by", None)
    ingest_type = request.args.get("ingest_type", None)
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = int(request.args.get("sort_order", -1))

    data = controller.db.get_paginated_tracks(
        page=page,
        limit=limit,
        search=search,
        genre=genre,
        download_status=download_status,
        moderation_status=moderation_status,
        added_by=added_by,
        ingest_type=ingest_type,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    collectors = controller.db.get_distinct_added_by()
    return jsonify({"success": True, "available_collectors": collectors, **data})


@app.route("/api/tracks/download_queue", methods=["GET"])
def api_get_download_queue():
    """Retrieve paginated and filtered download queue of tracks waiting for audio download."""
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    search = request.args.get("search", "").strip()
    genre = request.args.get("genre", "all")
    status = request.args.get("status", "pending")
    added_by = request.args.get("added_by", "all")
    get_all_ids = request.args.get("get_all_ids", "false").lower() == "true"

    if get_all_ids:
        ids = controller.db.get_download_queue_ids(
            search=search,
            genre=genre,
            status=status,
            added_by=added_by,
        )
        return jsonify({"success": True, "ids": ids, "total": len(ids)})

    data = controller.db.get_download_queue_paginated(
        page=page,
        limit=limit,
        search=search,
        genre=genre,
        status=status,
        added_by=added_by,
    )
    collectors = controller.db.get_distinct_added_by()
    return jsonify({"success": True, "available_collectors": collectors, **data})


@app.route("/api/tracks/<spotify_id>/inspect", methods=["GET"])
def api_inspect_track(spotify_id):
    """Retrieve full deep metadata, ID3 frames, file stats, and raw JSON document."""
    data = controller.db.get_track_full_metadata(spotify_id)
    if not data:
        return jsonify({"success": False, "error": "Track not found"}), 404
    return jsonify({"success": True, **data})


@app.route("/api/tracks/add", methods=["POST"])
def api_add_track():
    """Manually add a new track to database with strict validation and audit log."""
    body = request.get_json() or {}
    name = body.get("name", "").strip()
    artist = body.get("artist_name", "").strip()
    operator = session.get("user", {}).get("username", "admin")

    if not name or not artist:
        return jsonify({"success": False, "error": "Tên bài hát và Nghệ sĩ là bắt buộc!"}), 400

    track_id = body.get("spotify_id") or f"manual_{int(time.time()*1000)}"
    duration_sec = int(body.get("duration_sec", 180))
    if duration_sec <= 0:
        duration_sec = 180

    genres = body.get("genres", ["vpop"])
    if isinstance(genres, str):
        genres = [g.strip().lower() for g in genres.split(",") if g.strip()]

    new_track = {
        "spotify_id": track_id,
        "name": name,
        "artist_name": artist,
        "artists": [{"id": f"art_{int(time.time())}", "name": artist}],
        "album_name": body.get("album_name", "Single"),
        "album_spotify_id": f"alb_{int(time.time())}",
        "duration_ms": duration_sec * 1000,
        "duration_formatted": f"{duration_sec // 60}:{duration_sec % 60:02d}",
        "image_url": body.get("image_url", "") or "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=600&auto=format&fit=crop&q=80",
        "genres": genres,
        "popularity": max(0, min(100, int(body.get("popularity", 50)))),
        "download_status": "pending",
        "moderation_status": "approved",
        "added_by": operator,
        "ingest_type": "metadata_only",
        "created_at": datetime.utcnow(),
    }

    controller.db.upsert_track(new_track)
    controller.db.log_activity(
        username=operator,
        action="ADD_TRACK",
        status="SUCCESS",
        details=f"Thêm bài hát mới: '{name}' - {artist} ({duration_sec}s, {genres})",
        target=track_id,
    )
    controller.log(f"➕ Manually added track: '{name}' - {artist} (by @{operator})", level="success")
    controller.broadcast_stats()
    return jsonify({"success": True, "track": AuthManager._sanitize_doc(new_track)})


@app.route("/api/tracks/<spotify_id>", methods=["PUT"])
def api_update_track(spotify_id):
    """Update track metadata and lyrics with audit log."""
    body = request.get_json() or {}
    operator = session.get("user", {}).get("username", "admin")
    existing_track = controller.db.get_track(spotify_id)
    if not existing_track:
        return jsonify({"success": False, "error": "Track not found"}), 404

    update_fields = {}
    changes = []

    if "name" in body and body["name"].strip():
        update_fields["name"] = body["name"].strip()
        changes.append(f"Tên: '{body['name'].strip()}'")
    if "artist_name" in body and body["artist_name"].strip():
        update_fields["artist_name"] = body["artist_name"].strip()
        changes.append(f"Nghệ sĩ: '{body['artist_name'].strip()}'")
    if "album_name" in body:
        update_fields["album_name"] = body["album_name"].strip()
        changes.append(f"Album: '{body['album_name'].strip()}'")
    if "genres" in body:
        genres = body["genres"]
        if isinstance(genres, str):
            genres = [g.strip().lower() for g in genres.split(",") if g.strip()]
        update_fields["genres"] = genres
        changes.append(f"Thể loại: {genres}")
    if "popularity" in body:
        update_fields["popularity"] = max(0, min(100, int(body["popularity"])))
        changes.append(f"Độ hot: {update_fields['popularity']}")
    if "moderation_status" in body:
        update_fields["moderation_status"] = body["moderation_status"]
        changes.append(f"Duyệt: {body['moderation_status']}")
    if "lyrics_plain" in body:
        update_fields["lyrics_plain"] = body["lyrics_plain"]
    if "lyrics_synced" in body:
        update_fields["lyrics_synced"] = body["lyrics_synced"]
        update_fields["has_synced_lyrics"] = bool(body["lyrics_synced"])
        changes.append("Cập nhật lời .lrc")

        # Also write to local .lrc file if present
        if existing_track.get("lrc_path"):
            lrc_file = settings.BASE_DIR / existing_track["lrc_path"]
            try:
                with open(lrc_file, "w", encoding="utf-8") as f:
                    f.write(body["lyrics_synced"])
            except Exception as e:
                logger.warning(f"Failed to update lrc file: {e}")

    ok = controller.db.update_track_metadata(spotify_id, update_fields)
    if ok:
        controller.db.log_activity(
            username=operator,
            action="UPDATE_TRACK",
            status="SUCCESS",
            details=f"Cập nhật '{existing_track.get('name')}': {', '.join(changes)}",
            target=spotify_id,
        )
        controller.log(f"✏️ Updated metadata for track: {spotify_id} (by @{operator})", level="info")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Track not found"}), 404


@app.route("/api/tracks/<spotify_id>", methods=["DELETE"])
def api_delete_track(spotify_id):
    """Delete a track and its audio file with audit log."""
    operator = session.get("user", {}).get("username", "admin")
    existing_track = controller.db.get_track(spotify_id)
    if not existing_track:
        return jsonify({"success": False, "error": "Track not found"}), 404

    track_name = existing_track.get("name", spotify_id)
    ok = controller.db.delete_track(spotify_id, delete_audio_file=True)
    if ok:
        controller.db.log_activity(
            username=operator,
            action="DELETE_TRACK",
            status="SUCCESS",
            details=f"Xóa vĩnh viễn bài hát '{track_name}' khỏi Database & Ổ đĩa",
            target=spotify_id,
        )
        controller.log(f"🗑️ Deleted track '{track_name}' ({spotify_id}) by @{operator}.", level="warning")
        controller.broadcast_stats()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Track not found"}), 404


@app.route("/api/tracks/moderate", methods=["POST"])
def api_moderate_tracks():
    """Approve / Reject / Flag tracks with audit log."""
    body = request.get_json() or {}
    spotify_ids = body.get("spotify_ids", [])
    status = body.get("status", "approved")
    reviewer = session.get("user", {}).get("username", "admin")

    if not spotify_ids:
        return jsonify({"success": False, "error": "No tracks provided"}), 400

    modified = controller.db.bulk_moderate_tracks(spotify_ids, status=status, reviewer=reviewer)
    controller.db.log_activity(
        username=reviewer,
        action="MODERATE_TRACKS",
        status="SUCCESS",
        details=f"Chuyển trạng thái kiểm duyệt thành '{status.upper()}' cho {modified} bài hát",
        target=f"{len(spotify_ids)} tracks",
    )
    controller.log(f"🛡️ Moderation: Set {status.upper()} for {modified} tracks (by @{reviewer}).", level="info")
    return jsonify({"success": True, "modified_count": modified})


@app.route("/api/tracks/bulk_delete", methods=["POST"])
def api_bulk_delete_tracks():
    """Bulk delete tracks with audit log."""
    body = request.get_json() or {}
    spotify_ids = body.get("spotify_ids", [])
    operator = session.get("user", {}).get("username", "admin")

    if not spotify_ids:
        return jsonify({"success": False, "error": "No tracks provided"}), 400

    deleted = controller.db.bulk_delete_tracks(spotify_ids, delete_audio_files=True)
    controller.db.log_activity(
        username=operator,
        action="BULK_DELETE",
        status="SUCCESS",
        details=f"Xóa hàng loạt {deleted} bài hát và file MP3 tương ứng",
        target=f"{deleted} tracks",
    )
    controller.log(f"🗑️ Bulk deleted {deleted} tracks from DB and Storage (by @{operator}).", level="warning")
    controller.broadcast_stats()
    return jsonify({"success": True, "deleted_count": deleted})


@app.route("/api/tracks/<spotify_id>/redownload", methods=["POST"])
def api_redownload_track(spotify_id):
    """Trigger individual audio re-download for single track."""
    operator = session.get("user", {}).get("username", "admin")
    track = controller.db.get_track(spotify_id)
    if not track:
        return jsonify({"success": False, "error": "Track not found"}), 404

    def _redownload_worker():
        try:
            controller.log(f"⚡ Re-downloading audio for: {track.get('name')} - {track.get('artist_name')}...")
            res = controller.dm.download_single_track(track)
            if res.get("status") == "completed":
                controller.db.update_track_download_status(
                    spotify_id=spotify_id,
                    status="completed",
                    local_path=res.get("file_path"),
                    file_size_bytes=res.get("file_size_bytes", 0),
                    lyrics_plain=res.get("lyrics_plain"),
                    lyrics_synced=res.get("lyrics_synced"),
                    lrc_path=res.get("lrc_path"),
                )
                controller.db.log_activity(
                    username=operator,
                    action="REDOWNLOAD_TRACK",
                    status="SUCCESS",
                    details=f"Tải lại thành công: '{track.get('name')}' (320kbps MP3)",
                    target=spotify_id,
                )
                controller.log(f"✅ Successfully re-downloaded: {track.get('name')}", level="success")
                controller.broadcast_stats()
                socketio.emit("track_redownloaded", {"spotify_id": spotify_id, "success": True})
            else:
                controller.db.log_activity(
                    username=operator,
                    action="REDOWNLOAD_TRACK",
                    status="FAILED",
                    details=f"Tải lại thất bại: {res.get('error')}",
                    target=spotify_id,
                )
                controller.log(f"❌ Re-download failed: {res.get('error')}", level="error")
                socketio.emit("track_redownloaded", {"spotify_id": spotify_id, "success": False, "error": res.get("error")})
        except Exception as ex:
            controller.log(f"Re-download exception: {ex}", level="error")

    threading.Thread(target=_redownload_worker, daemon=True).start()
    return jsonify({"success": True, "message": "Re-download started in background"})


# ─── System Audit Logs REST APIs ─────────────────────────────

@app.route("/api/logs", methods=["GET"])
def api_get_system_logs():
    """Retrieve paginated and filtered persistent audit logs."""
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    username = request.args.get("user", None)
    action = request.args.get("action", None)
    status = request.args.get("status", None)
    search = request.args.get("search", "").strip()
    date_filter = request.args.get("date", None)

    data = controller.db.get_paginated_logs(
        page=page,
        limit=limit,
        username=username,
        action=action,
        status=status,
        search=search,
        date_filter=date_filter,
    )
    users = controller.db.get_distinct_log_users()
    actions = controller.db.get_distinct_log_actions()
    return jsonify({"success": True, "available_users": users, "available_actions": actions, **data})


@app.route("/api/logs/daily_summary", methods=["GET"])
def api_get_daily_log_summary():
    """Retrieve daily summary list of log events and disk log files."""
    summary = controller.db.get_daily_log_summary()
    return jsonify({"success": True, "daily_summary": summary, "total_days": len(summary)})


@app.route("/api/logs/files", methods=["GET"])
def api_get_log_files():
    """List physical daily log files on disk."""
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    files = []
    if log_dir.exists():
        for f in sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True):
            files.append({
                "filename": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "size_bytes": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
    return jsonify({"success": True, "files": files, "total": len(files)})


@app.route("/api/logs/file/<filename>", methods=["GET"])
def api_read_log_file(filename):
    """Read text lines from a physical log file on disk."""
    safe_name = os.path.basename(filename)
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    file_path = log_dir / safe_name

    if not file_path.exists() or not file_path.is_file():
        return jsonify({"success": False, "error": f"File log '{safe_name}' không tồn tại"}), 404

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        tail_limit = int(request.args.get("limit", 1000))
        total_lines = len(lines)
        if total_lines > tail_limit:
            selected_lines = lines[-tail_limit:]
        else:
            selected_lines = lines

        return jsonify({
            "success": True,
            "filename": safe_name,
            "total_lines": total_lines,
            "lines_shown": len(selected_lines),
            "content": "".join(selected_lines),
            "size_kb": round(file_path.stat().st_size / 1024, 1),
        })
    except Exception as ex:
        return jsonify({"success": False, "error": str(ex)}), 500


@app.route("/api/logs/download_raw/<filename>", methods=["GET"])
def api_download_raw_log(filename):
    """Download physical log file from disk."""
    safe_name = os.path.basename(filename)
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    return send_from_directory(str(log_dir), safe_name, as_attachment=True)


@app.route("/api/logs/export", methods=["GET"])
def api_export_system_logs():
    """Export audit logs in JSON format with optional date filtering."""
    date_filter = request.args.get("date", None)
    query = {}
    if date_filter and date_filter.strip() and date_filter.lower() != "all":
        try:
            dt_start = datetime.strptime(date_filter.strip(), "%Y-%m-%d")
            dt_end = dt_start.replace(hour=23, minute=59, second=59, microsecond=999999)
            query["timestamp"] = {"$gte": dt_start, "$lte": dt_end}
        except Exception:
            pass

    logs = list(controller.db.db.system_logs.find(query, {"_id": 0}).sort("timestamp", -1))
    from src.storage.auth_manager import AuthManager
    return jsonify({
        "success": True,
        "date": date_filter or "all",
        "total": len(logs),
        "logs": AuthManager._sanitize_doc(logs),
    })


# ─── Smart Trends & Live Music Discovery API ─────────────────
trend_mgr = TrendManager(spotify_collector=SpotifyCollector())

@app.route("/api/trends", methods=["GET"])
def api_get_trends():
    """Retrieve smart trending keywords, viral artists, new releases, and top playlists."""
    force = request.args.get("refresh", "false").lower() == "true"
    trends = trend_mgr.get_trends(force_refresh=force)
    return jsonify({"success": True, **trends})


# ─── Proxy Management REST APIs ──────────────────────────────

@app.route("/api/proxies", methods=["GET"])
def api_get_proxies():
    """Retrieve all proxies from MongoDB."""
    proxies = controller.db.get_all_proxies()
    return jsonify({"success": True, "proxies": proxies, "total": len(proxies)})


@app.route("/api/proxies", methods=["POST"])
def api_save_proxy():
    """Add or update a proxy configuration in MongoDB with audit log."""
    body = request.get_json() or {}
    operator = session.get("user", {}).get("username", "admin")
    host = body.get("host", "").strip()
    port = int(body.get("port", 8080))
    protocol = body.get("protocol", "http").lower().strip()

    if not host or port <= 0:
        return jsonify({"success": False, "error": "Host và Port proxy không được để trống!"}), 400

    body["added_by"] = body.get("added_by") or operator
    ok = controller.db.upsert_proxy(body)
    if ok:
        controller.pm.sync_from_db()
        controller.db.log_activity(
            username=operator,
            action="UPDATE_PROXY",
            status="SUCCESS",
            details=f"Lưu proxy [{protocol.upper()}]: {host}:{port}",
            target=f"{host}:{port}",
        )
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Không thể lưu proxy"}), 500


@app.route("/api/proxies/<proxy_id>", methods=["DELETE"])
def api_delete_proxy(proxy_id):
    """Delete a proxy configuration from MongoDB with audit log."""
    operator = session.get("user", {}).get("username", "admin")
    existing = controller.db.get_proxy(proxy_id)
    if not existing:
        return jsonify({"success": False, "error": "Proxy không tồn tại"}), 404

    ok = controller.db.delete_proxy(proxy_id)
    if ok:
        controller.pm.sync_from_db()
        controller.db.log_activity(
            username=operator,
            action="DELETE_PROXY",
            status="SUCCESS",
            details=f"Xóa proxy '{existing.get('name')}' ({existing.get('url')})",
            target=proxy_id,
        )
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Không thể xóa proxy"}), 500


@app.route("/api/proxies/<proxy_id>/toggle", methods=["POST"])
def api_toggle_proxy(proxy_id):
    """Toggle active state of a proxy."""
    body = request.get_json() or {}
    is_active = bool(body.get("is_active", True))
    ok = controller.db.toggle_proxy(proxy_id, is_active)
    if ok:
        controller.pm.sync_from_db()
        return jsonify({"success": True, "is_active": is_active})
    return jsonify({"success": False, "error": "Proxy không tồn tại"}), 404


@app.route("/api/proxies/<proxy_id>/test", methods=["POST"])
def api_test_proxy(proxy_id):
    """Perform live speed and latency ping test for a single proxy."""
    proxy = controller.db.get_proxy(proxy_id)
    if not proxy:
        return jsonify({"success": False, "error": "Proxy không tồn tại"}), 404

    url = proxy.get("url", "")
    res = ProxyManager.test_proxy_connection(url)
    controller.db.update_proxy_status(
        proxy_id=proxy_id,
        status=res.get("status", "dead"),
        latency_ms=res.get("latency_ms", 0),
        error=res.get("error"),
    )
    return jsonify({"success": True, "proxy_id": proxy_id, **res})


@app.route("/api/proxies/test_all", methods=["POST"])
def api_test_all_proxies():
    """Test all proxies in pool and update their status in MongoDB."""
    proxies = controller.db.get_all_proxies()
    results = []
    for p in proxies:
        pid = p.get("id")
        res = ProxyManager.test_proxy_connection(p.get("url", ""))
        controller.db.update_proxy_status(
            proxy_id=pid,
            status=res.get("status", "dead"),
            latency_ms=res.get("latency_ms", 0),
            error=res.get("error"),
        )
        results.append({"id": pid, **res})
    controller.pm.sync_from_db()
    return jsonify({"success": True, "results": results, "total": len(results)})


# ─── Spotify App Pool REST APIs ──────────────────────────────

@app.route("/api/spotify_apps", methods=["GET"])
def api_get_spotify_apps():
    """Retrieve all Spotify Apps from MongoDB."""
    apps = controller.db.get_all_spotify_apps()
    return jsonify({"success": True, "apps": apps, "total": len(apps)})


@app.route("/api/spotify_apps", methods=["POST"])
def api_save_spotify_app():
    """Add or update a Spotify App in MongoDB with audit log."""
    body = request.get_json() or {}
    operator = session.get("user", {}).get("username", "admin")
    client_id = body.get("client_id", "").strip()
    client_secret = body.get("client_secret", "").strip()
    name = body.get("name", "").strip() or "Spotify App"

    if not client_id or not client_secret:
        return jsonify({"success": False, "error": "Client ID và Client Secret là bắt buộc!"}), 400

    body["added_by"] = body.get("added_by") or operator
    ok = controller.db.upsert_spotify_app(body)
    if ok:
        controller.db.log_activity(
            username=operator,
            action="UPDATE_SPOTIFY_APP",
            status="SUCCESS",
            details=f"Lưu Spotify App: '{name}' (Owner: @{body['added_by']})",
            target=client_id,
        )
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Không thể lưu Spotify App"}), 500


@app.route("/api/spotify_apps/<app_id>", methods=["DELETE"])
def api_delete_spotify_app(app_id):
    """Delete a Spotify App from MongoDB with audit log."""
    operator = session.get("user", {}).get("username", "admin")
    existing = controller.db.get_spotify_app(app_id)
    if not existing:
        return jsonify({"success": False, "error": "Spotify App không tồn tại"}), 404

    ok = controller.db.delete_spotify_app(app_id)
    if ok:
        controller.db.log_activity(
            username=operator,
            action="DELETE_SPOTIFY_APP",
            status="SUCCESS",
            details=f"Xóa Spotify App '{existing.get('name')}'",
            target=app_id,
        )
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Không thể xóa Spotify App"}), 500


@app.route("/api/spotify_apps/<app_id>/set_active", methods=["POST"])
def api_set_active_spotify_app(app_id):
    """Set an app as the primary active Spotify credentials."""
    operator = session.get("user", {}).get("username", "admin")
    ok = controller.db.set_active_spotify_app(app_id)
    if ok:
        app_doc = controller.db.get_spotify_app(app_id)
        if app_doc:
            # Reconfigure global settings / collector
            settings.SPOTIFY_CLIENT_ID = app_doc.get("client_id", settings.SPOTIFY_CLIENT_ID)
            settings.SPOTIFY_CLIENT_SECRET = app_doc.get("client_secret", settings.SPOTIFY_CLIENT_SECRET)
            if app_doc.get("sp_dc"):
                settings.SPOTIFY_SP_DC = app_doc.get("sp_dc")

        controller.db.log_activity(
            username=operator,
            action="SET_ACTIVE_SPOTIFY_APP",
            status="SUCCESS",
            details=f"Kích hoạt Spotify App chính: '{app_doc.get('name') if app_doc else app_id}'",
            target=app_id,
        )
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Spotify App không tồn tại"}), 404


@app.route("/api/spotify_apps/<app_id>/test", methods=["POST"])
def api_test_spotify_app(app_id):
    """Test Spotify connection and inspect if account has Premium subscription."""
    app_doc = controller.db.get_spotify_app(app_id)
    if not app_doc:
        return jsonify({"success": False, "error": "Spotify App không tồn tại"}), 404

    client_id = app_doc.get("client_id", "")
    client_secret = app_doc.get("client_secret", "")
    sp_dc = app_doc.get("sp_dc", "")

    res = SpotifyCollector.test_spotify_app_credentials(
        client_id=client_id,
        client_secret=client_secret,
        sp_dc=sp_dc,
    )

    controller.db.update_spotify_app_status(
        app_id=app_id,
        status=res.get("status", "invalid"),
        is_premium=res.get("is_premium", False),
        account_type=res.get("account_type", "Developer API"),
        latency_ms=res.get("latency_ms", 0),
        error=res.get("error"),
    )

    return jsonify({"success": True, "app_id": app_id, **res})


# ─── Network Shield, WARP, Tailscale & Fingerprint Studio REST APIs ─────────

@app.route("/api/network/shield_status", methods=["GET"])
def api_get_network_shield_status():
    """Query current network protection, egress IP, WARP, Tailscale, and active Fingerprint."""
    warp_status = WarpController.get_status()
    tailscale_status = TailscaleController.get_status()
    active_fp = FingerprintGenerator.get_active_profile()

    # Current egress probe (Prioritize Proxy Pool or WARP Gateway if connected)
    active_proxy = controller.pm.get_proxy() if controller.pm.enabled else None
    if not active_proxy and warp_status.get("is_connected"):
        active_proxy = "socks5://127.0.0.1:40000"

    egress_info = ProxyManager.inspect_egress_ip(proxy_url=active_proxy)
    strategy = getattr(controller.pm, "strategy", "round-robin")

    is_protected = (
        warp_status.get("is_connected") or
        (active_proxy is not None and egress_info.get("ip") not in ("158.178.247.33", "Unknown", "Failed to connect"))
    )

    return jsonify({
        "success": True,
        "host_ip": "158.178.247.33",
        "host_isp": "Oracle Corporation",
        "host_country": "SG",
        "egress_ip": egress_info.get("ip", "104.28.222.43" if warp_status.get("is_connected") else "158.178.247.33"),
        "egress_isp": egress_info.get("isp", "Cloudflare Anycast" if warp_status.get("is_connected") else "Oracle Cloud"),
        "egress_country": egress_info.get("country", "SG"),
        "is_protected": is_protected,
        "latency_ms": egress_info.get("latency_ms", 25),
        "rotation_strategy": strategy,
        "warp": warp_status,
        "tailscale": tailscale_status,
        "fingerprint": active_fp,
    })


@app.route("/api/network/strategy", methods=["POST"])
def api_set_network_strategy():
    """Set proxy rotation strategy."""
    body = request.get_json() or {}
    strategy = body.get("strategy", "round-robin").lower()
    controller.pm.strategy = strategy
    return jsonify({"success": True, "strategy": strategy})


@app.route("/api/network/warp/status", methods=["GET"])
def api_get_warp_status():
    """Get Cloudflare WARP status."""
    return jsonify({"success": True, **WarpController.get_status()})


@app.route("/api/network/warp/toggle", methods=["POST"])
def api_toggle_warp():
    """Toggle Cloudflare WARP connection."""
    body = request.get_json() or {}
    enable = bool(body.get("enable", True))
    if enable:
        ok = WarpController.connect()
    else:
        ok = WarpController.disconnect()
    controller.pm.sync_from_db()
    return jsonify({"success": True, "connected": ok, **WarpController.get_status()})


@app.route("/api/network/tailscale/status", methods=["GET"])
def api_get_tailscale_status():
    """Get Tailscale connection and exit nodes status."""
    return jsonify({"success": True, **TailscaleController.get_status()})


@app.route("/api/network/tailscale/connect", methods=["POST"])
def api_connect_tailscale():
    """Connect to Tailscale using Auth Key."""
    body = request.get_json() or {}
    auth_key = body.get("auth_key", "").strip()
    exit_node = body.get("exit_node", "").strip() or None
    if not auth_key:
        return jsonify({"success": False, "error": "Auth Key không được để trống!"}), 400

    ok = TailscaleController.connect(auth_key=auth_key, exit_node=exit_node)
    controller.pm.sync_from_db()
    return jsonify({"success": ok, **TailscaleController.get_status()})


@app.route("/api/network/tailscale/exit_node", methods=["POST"])
def api_set_tailscale_exit_node():
    """Switch Tailscale exit node."""
    body = request.get_json() or {}
    node_ip_or_name = body.get("exit_node", "").strip()
    ok = TailscaleController.set_exit_node(node_ip_or_name if node_ip_or_name else None)
    controller.pm.sync_from_db()
    return jsonify({"success": ok, **TailscaleController.get_status()})


@app.route("/api/network/tailscale/disconnect", methods=["POST"])
def api_disconnect_tailscale():
    """Disconnect Tailscale."""
    ok = TailscaleController.disconnect()
    controller.pm.sync_from_db()
    return jsonify({"success": ok, **TailscaleController.get_status()})


@app.route("/api/network/fingerprints", methods=["GET"])
def api_get_fingerprints():
    """Retrieve all preset and custom fingerprint profiles from database."""
    profiles = controller.db.get_all_fingerprints()
    if not profiles:
        FingerprintGenerator.sync_with_db()
        profiles = controller.db.get_all_fingerprints()
    active_fp = FingerprintGenerator.get_active_profile()
    return jsonify({
        "success": True,
        "profiles": profiles,
        "active_profile": active_fp,
        "total": len(profiles),
    })


@app.route("/api/network/fingerprints", methods=["POST"])
def api_save_custom_fingerprint():
    """Add or update a custom fingerprint profile in MongoDB with automated pre-flight testing."""
    body = request.get_json() or {}
    operator = session.get("user", {}).get("username", "admin")
    name = body.get("name", "").strip()
    user_agent = body.get("user_agent", "").strip()
    os_name = body.get("os", "Windows").strip()

    if not name or not user_agent:
        return jsonify({"success": False, "error": "Tên hồ sơ và chuỗi User-Agent không được để trống!"}), 400

    body["added_by"] = operator
    body["is_custom"] = True

    # Run automated pre-flight test before adding to database
    preflight = FingerprintGenerator.preflight_test(profile=body)
    body["status"] = preflight.get("status", "untested")
    body["preflight_passed"] = preflight.get("passed", False)
    body["last_latency_ms"] = preflight.get("latency_ms", 0)

    ok = controller.db.upsert_fingerprint(body)
    if ok:
        FingerprintGenerator.sync_with_db()
        controller.db.log_activity(
            username=operator,
            action="CREATE_FINGERPRINT_PROFILE",
            status="SUCCESS" if preflight.get("passed") else "WARNING",
            details=f"Tạo hồ sơ giả lập '{name}' (Pre-flight: {preflight.get('status')}, Ping: {preflight.get('latency_ms')}ms)",
            target=body.get("id"),
        )
        return jsonify({
            "success": True,
            "preflight": preflight,
            "message": f"Đã lưu hồ sơ '{name}' thành công! (Pre-flight: {preflight.get('status')})"
        })
    return jsonify({"success": False, "error": "Không thể lưu hồ sơ giả lập"}), 500


@app.route("/api/network/fingerprints/<profile_id>", methods=["DELETE"])
def api_delete_fingerprint(profile_id):
    """Delete a custom fingerprint profile."""
    operator = session.get("user", {}).get("username", "admin")
    profile = controller.db.get_fingerprint(profile_id)
    if not profile:
        return jsonify({"success": False, "error": "Hồ sơ không tồn tại"}), 404

    if not profile.get("is_custom", True):
        return jsonify({"success": False, "error": "Không thể xóa hồ sơ mặc định của hệ thống!"}), 400

    ok = controller.db.delete_fingerprint(profile_id)
    if ok:
        FingerprintGenerator.sync_with_db()
        controller.db.log_activity(
            username=operator,
            action="DELETE_FINGERPRINT_PROFILE",
            status="SUCCESS",
            details=f"Xóa hồ sơ giả lập '{profile.get('name')}'",
            target=profile_id,
        )
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Không thể xóa hồ sơ"}), 500


@app.route("/api/network/fingerprints/<profile_id>/preflight_test", methods=["POST"])
def api_preflight_test_fingerprint(profile_id):
    """Perform automated pre-flight test for a specific profile."""
    profile = controller.db.get_fingerprint(profile_id)
    if not profile:
        for p in FingerprintGenerator.PROFILES:
            if p["id"] == profile_id:
                profile = p
                break

    if not profile:
        return jsonify({"success": False, "error": "Hồ sơ không tồn tại"}), 404

    active_proxy = controller.pm.get_proxy() if controller.pm.enabled else None
    result = FingerprintGenerator.preflight_test(profile=profile, proxy_url=active_proxy)
    return jsonify({"success": True, **result})


@app.route("/api/network/fingerprints/<profile_id>/activate", methods=["POST"])
def api_activate_fingerprint(profile_id):
    """Auto-test and activate a fingerprint profile if healthy."""
    operator = session.get("user", {}).get("username", "admin")
    profile = controller.db.get_fingerprint(profile_id)
    if not profile:
        for p in FingerprintGenerator.PROFILES:
            if p["id"] == profile_id:
                profile = p
                break

    if not profile:
        return jsonify({"success": False, "error": "Hồ sơ không tồn tại"}), 404

    active_proxy = controller.pm.get_proxy() if controller.pm.enabled else None
    preflight = FingerprintGenerator.preflight_test(profile=profile, proxy_url=active_proxy)

    if not preflight.get("passed"):
        return jsonify({
            "success": False,
            "error": f"Kiểm tra Pre-flight thất bại ({preflight.get('error') or 'Lỗi kết nối'}). Không thể kích hoạt hồ sơ này!",
            "preflight": preflight,
        }), 400

    ok = FingerprintGenerator.set_active_profile(profile_id)
    if ok:
        active = FingerprintGenerator.get_active_profile()
        controller.db.log_activity(
            username=operator,
            action="ACTIVATE_FINGERPRINT",
            status="SUCCESS",
            details=f"Kích hoạt hồ sơ giả lập '{active.get('name')}' (Pre-flight passed)",
            target=profile_id,
        )
        return jsonify({
            "success": True,
            "active_profile": active,
            "preflight": preflight,
            "message": f"Đã kiểm thử đạt chuẩn và kích hoạt hồ sơ '{active.get('name')}'!"
        })
    return jsonify({"success": False, "error": "Không thể kích hoạt hồ sơ"}), 500


@app.route("/api/network/health_watchdog", methods=["GET"])
def api_get_network_health_watchdog():
    """
    Live real-time connectivity watchdog checking:
    1. Oracle host outbound connection
    2. Cloudflare WARP SOCKS5 Gateway
    3. Tailscale Mesh Tunnel & Exit Node
    4. Active Proxy Pool latency
    5. Upstream YouTube/Spotify API status
    Detects and reports connection drops immediately.
    """
    import socket
    import requests

    watchdog_report = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "is_healthy": True,
        "alerts": [],
        "services": {},
    }

    # 1. Probe Host Internet Outbound
    try:
        r_out = requests.get("https://1.1.1.1", timeout=3)
        watchdog_report["services"]["internet"] = {"status": "online", "latency_ms": int(r_out.elapsed.total_seconds() * 1000)}
    except Exception as e:
        watchdog_report["is_healthy"] = False
        watchdog_report["alerts"].append(f"Mất kết nối Internet chính máy chủ: {e}")
        watchdog_report["services"]["internet"] = {"status": "down", "error": str(e)}

    # 2. Probe Cloudflare WARP
    warp_status = WarpController.get_status()
    if warp_status.get("is_connected"):
        try:
            r_warp = requests.get(
                "https://cloudflare.com/cdn-cgi/trace",
                proxies={"http": "socks5://127.0.0.1:40000", "https": "socks5://127.0.0.1:40000"},
                timeout=4
            )
            warp_ip = "104.28.222.43"
            for line in r_warp.text.splitlines():
                if line.startswith("ip="):
                    warp_ip = line.split("=", 1)[1].strip()
                    break
            watchdog_report["services"]["warp"] = {"status": "online", "ip": warp_ip}
        except Exception as e:
            watchdog_report["alerts"].append(f"Cảnh báo: Cloudflare WARP Gateway 127.0.0.1:40000 không phản hồi: {e}")
            watchdog_report["services"]["warp"] = {"status": "degraded", "error": str(e)}
    else:
        watchdog_report["services"]["warp"] = {"status": "disabled"}

    # 3. Probe Active Proxy
    if controller.pm.enabled and controller.pm.proxies:
        active_prx = controller.pm.get_proxy()
        if active_prx:
            prx_res = ProxyManager.test_proxy_connection(active_prx, timeout=4)
            if prx_res.get("status") != "alive":
                watchdog_report["alerts"].append(f"Cảnh báo: Proxy đang dùng ({active_prx}) bị mất kết nối!")
                watchdog_report["services"]["proxy"] = {"status": "down", "proxy": active_prx, "error": prx_res.get("error")}
            else:
                watchdog_report["services"]["proxy"] = {"status": "alive", "proxy": active_prx, "latency_ms": prx_res.get("latency_ms")}
    else:
        watchdog_report["services"]["proxy"] = {"status": "direct"}

    # 4. Probe YouTube Music / Spotify Streaming API
    try:
        r_yt = requests.get("https://www.youtube.com/generate_204", timeout=4)
        watchdog_report["services"]["youtube"] = {"status": "reachable", "code": r_yt.status_code}
    except Exception as e:
        watchdog_report["alerts"].append(f"Cảnh báo: Không thể kết nối tới YouTube CDN: {e}")
        watchdog_report["services"]["youtube"] = {"status": "unreachable", "error": str(e)}

    # If any alert exists, emit socket alert to dashboard
    if watchdog_report["alerts"]:
        socketio.emit("network_connection_lost", {
            "alerts": watchdog_report["alerts"],
            "timestamp": time.strftime("%H:%M:%S")
        })

    return jsonify({"success": True, **watchdog_report})



@app.route("/api/stats")
def get_stats():
    """API endpoint to get instant metrics."""
    return jsonify(
        {
            "stats": controller.db.get_statistics(),
            "storage": controller.fm.get_storage_stats(),
            "sessions": controller.sm.get_session_stats(),
            "health": controller.health.get_status(),
            "proxy": controller.pm.get_status(),
            "current_user": session.get("user"),
        }
    )


# ─── Concurrency & System Lock REST Endpoints ───────────────

@app.route("/api/system/locks", methods=["GET"])
def api_get_system_locks():
    """Retrieve all active concurrency locks and their remaining TTL lease time."""
    now = datetime.utcnow()
    locks = []
    if controller.db.is_connected():
        try:
            for doc in controller.db.db.system_locks.find({}, {"_id": 0}):
                exp = doc.get("expires_at")
                if exp and exp > now:
                    doc["time_left_sec"] = int((exp - now).total_seconds())
                    locks.append(doc)
        except Exception:
            pass

    return jsonify({
        "success": True,
        "locks": locks,
        "total": len(locks),
        "pipeline_running": controller.is_running,
        "active_task": controller.active_task_name,
    })


@app.route("/api/system/locks/force_unlock", methods=["POST"])
def api_force_unlock():
    """Force release an active system lock in case of emergency (Admin only)."""
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"success": False, "error": "Chỉ Quản trị viên mới có quyền mở khóa cưỡng bức!"}), 403

    body = request.get_json() or {}
    lock_name = body.get("lock_name", "pipeline_global_lock")
    lock_manager.release_lock(lock_name)
    controller.is_running = False
    controller.active_task_name = "Idle"
    socketio.emit("task_status", {"task": "Idle", "running": False})
    controller.broadcast_stats()
    controller.log(f"🔓 Quản trị viên @{user.get('username')} đã cưỡng bức giải phóng khóa '{lock_name}'.", level="warning")
    return jsonify({"success": True, "message": f"Đã giải phóng khóa '{lock_name}' thành công!"})


# ─── Multi-Job Parallel Worker Queue REST Endpoints ──────────

@app.route("/api/jobs/active", methods=["GET"])
def api_get_active_jobs():
    """Retrieve list of all active concurrent crawl and download jobs."""
    jobs = controller.get_active_jobs_list()
    return jsonify({
        "success": True,
        "jobs": jobs,
        "total": len(jobs),
        "is_running": controller.is_running,
    })


@app.route("/api/jobs/<job_id>/pause", methods=["POST"])
def api_pause_job(job_id):
    """Pause a specific running job."""
    user = session.get("user", {})
    operator = user.get("username", "admin")
    ok = controller.pause_job(job_id, operator_name=operator)
    if ok:
        return jsonify({"success": True, "message": f"Đã tạm dừng tác vụ {job_id}"})
    return jsonify({"success": False, "error": "Không tìm thấy tác vụ hoặc tác vụ đã kết thúc"}), 404


@app.route("/api/jobs/<job_id>/resume", methods=["POST"])
def api_resume_job(job_id):
    """Resume a paused job."""
    user = session.get("user", {})
    operator = user.get("username", "admin")
    ok = controller.resume_job(job_id, operator_name=operator)
    if ok:
        return jsonify({"success": True, "message": f"Đã tiếp tục tác vụ {job_id}"})
    return jsonify({"success": False, "error": "Không tìm thấy tác vụ hoặc tác vụ đã kết thúc"}), 404


@app.route("/api/jobs/<job_id>/stop", methods=["POST"])
def api_stop_job(job_id):
    """Stop/Cancel a specific job and release its claimed tracks."""
    user = session.get("user", {})
    operator = user.get("username", "admin")
    ok = controller.stop_job(job_id, operator_name=operator)
    if ok:
        return jsonify({"success": True, "message": f"Đã dừng tác vụ {job_id} và giải phóng hàng đợi bài hát"})
    return jsonify({"success": False, "error": "Không tìm thấy tác vụ hoặc tác vụ đã kết thúc"}), 404


# ─── WebSocket Events ────────────────────────────────────────

@socketio.on("connect")
def handle_connect():
    """Client connected: emit initial state and statistics."""
    controller.broadcast_stats()


@socketio.on("direct_url_ingest")
def handle_direct_url_ingest(data):
    """Ingest track directly from any yt-dlp supported URL (YouTube, SoundCloud, TikTok, direct MP3)."""
    url = data.get("url", "").strip()
    title = data.get("title", "").strip() or None
    artist = data.get("artist", "").strip() or None
    genre = data.get("genre", "pop") or "pop"

    if not url:
        controller.log("Please provide a valid direct URL.", level="warning")
        return

    controller.log(f"🌐 Ingesting direct URL: {url}...")
    socketio.emit("task_status", {"task": f"Ingesting: {url[:35]}...", "running": True})

    def _ingest_worker():
        try:
            ok, track_dict, err = controller.dm.download_direct_url(
                url=url,
                custom_title=title,
                custom_artist=artist,
                genre=genre,
            )
            if ok and track_dict:
                controller.log(f"✅ Successfully ingested: {track_dict.get('artist_name')} - {track_dict.get('name')} (320k MP3 + Lyrics)!", level="success")
                socketio.emit("import_success", {
                    "new_count": 1,
                    "updated_count": 0,
                    "total_imported": 1,
                })
                controller.broadcast_stats()
            else:
                controller.log(f"❌ Direct URL ingestion failed: {err}", level="error")
        except Exception as ex:
            controller.log(f"Direct URL error: {ex}", level="error")
        finally:
            socketio.emit("task_status", {"task": "Idle", "running": False})

    threading.Thread(target=_ingest_worker, daemon=True).start()


@socketio.on("search_preview")
def handle_search_preview(data):
    mode = data.get("mode", "artist")
    query = data.get("query", "").strip()
    genre = data.get("genre", None)
    limit = int(data.get("limit", 20))

    if not query and mode != "curated":
        controller.log("Please enter a query to preview search results.", level="warning")
        return

    controller.log(f"🔍 Searching & previewing tracks [Mode: {mode.upper()}, Query: '{query or 'Curated'}' (Limit: {limit})...")
    socketio.emit("task_status", {"task": f"Searching: {query or mode}", "running": True})

    def _preview_worker():
        try:
            collector = SpotifyCollector()
            raw_tracks = []
            if mode == "curated" and not query:
                playlists_path = settings.CONFIG_DIR / "playlists.json"
                if not playlists_path.exists():
                    playlists_path = settings.BASE_DIR / "config" / "playlists.json"
                with open(playlists_path, "r", encoding="utf-8") as f:
                    target_playlists = json.load(f).get("playlists", [])
                for pl in target_playlists[:3]:  # preview sample from first 3 playlists
                    tracks = collector.collect_playlist_tracks(pl.get("url"), max_tracks=5, default_genre=pl.get("genre"))
                    raw_tracks.extend(tracks)
            else:
                raw_tracks = collector.collect_custom(mode=mode, query=query, max_tracks=limit, default_genre=genre)

            # Check DB status for each track
            existing_db_tracks = controller.db.get_all_tracks()
            db_map = {t.get("spotify_id"): t for t in existing_db_tracks if t.get("spotify_id")}
            db_keys = {Deduplicator.normalize_comparison_key(t.get("name", ""), t.get("artist_name", "")): t for t in existing_db_tracks}

            preview_list = []
            for t in raw_tracks:
                sid = t.get("spotify_id")
                comp_key = Deduplicator.normalize_comparison_key(t.get("name", ""), t.get("artist_name", ""))
                
                db_item = db_map.get(sid) or db_keys.get(comp_key)
                if db_item:
                    dl_status = db_item.get("download_status", "pending")
                    if dl_status == "completed":
                        t["db_status"] = "downloaded"
                    elif dl_status == "failed":
                        t["db_status"] = "download_failed"
                    else:
                        t["db_status"] = "metadata_only"
                else:
                    t["db_status"] = "new"

                preview_list.append(t)

            controller.log(f"Found {len(preview_list)} track candidates for preview.", level="info")
            socketio.emit("search_results", {
                "tracks": preview_list,
                "query": query,
                "mode": mode,
                "genre": genre,
            })
        except Exception as ex:
            logger.error(f"Preview search failed: {ex}")
            controller.log(f"Preview search failed: {ex}", level="error")
            socketio.emit("search_results", {
                "tracks": [],
                "query": query,
                "mode": mode,
                "genre": genre,
                "error": str(ex),
            })
        finally:
            socketio.emit("task_status", {"task": "Idle", "running": False})

    threading.Thread(target=_preview_worker, daemon=True).start()


# ─── Cookie Upload & Headless VPS Management ─────────────────

@app.route("/api/upload_cookies", methods=["POST"])
def upload_cookies():
    """Upload cookies.txt for headless VPS/Docker deployment."""
    if "cookie_file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400
    file = request.files["cookie_file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "Empty filename"}), 400

    target_path = settings.CONFIG_DIR / "cookies.txt"
    file.save(str(target_path))
    settings.COOKIES_FILE = target_path
    controller.dm.cookies_path = target_path
    controller.log(f"🍪 Uploaded cookies.txt ({target_path.stat().st_size} bytes). Server authenticated.", level="success")
    return jsonify({"success": True, "size": target_path.stat().st_size})


def sync_active_cookie_to_disk():
    """Sync current active cookie from MongoDB to config/cookies.txt runtime files."""
    try:
        active_c = controller.db.get_active_cookie(service="youtube")
        if active_c and active_c.get("content"):
            content = active_c["content"].strip()
            for p in [settings.CONFIG_DIR / "cookies.txt", settings.DATA_DIR / "cookies.txt"]:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            settings.COOKIES_FILE = settings.CONFIG_DIR / "cookies.txt"
            controller.dm.cookies_path = settings.CONFIG_DIR / "cookies.txt"
            logger.info(f"🍪 Synced active YouTube cookie '{active_c.get('name')}' to disk.")
    except Exception as ex:
        logger.error(f"Error syncing active cookie to disk: {ex}")


# Initialize active cookie on startup
try:
    sync_active_cookie_to_disk()
except Exception:
    pass


# ─── Catalog Track REST Endpoints ────────────────────────────

@app.route("/api/tracks/<spotify_id>", methods=["DELETE"])
def delete_single_track(spotify_id):
    """Delete a track from MongoDB and disk."""
    ok = controller.db.delete_track(spotify_id)
    if ok:
        controller.log(f"🗑️ Đã xóa bài hát '{spotify_id}' khỏi hệ thống.", level="warning")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Không tìm thấy bài hát hoặc lỗi xóa"}), 404


@app.route("/api/tracks/bulk_delete", methods=["POST"])
def bulk_delete_tracks():
    """Delete multiple selected tracks."""
    data = request.get_json() or {}
    spotify_ids = data.get("spotify_ids", [])
    if not spotify_ids:
        return jsonify({"success": False, "error": "Danh sách bài hát rỗng"}), 400

    deleted = controller.db.delete_tracks_bulk(spotify_ids)
    controller.log(f"🗑️ Đã xóa hàng loạt {deleted}/{len(spotify_ids)} bài hát khỏi hệ thống.", level="warning")
    return jsonify({"success": True, "deleted": deleted, "total": len(spotify_ids)})


@app.route("/api/tracks/moderate", methods=["POST"])
def moderate_tracks():
    """Approve, flag, or reject tracks in bulk."""
    data = request.get_json() or {}
    spotify_ids = data.get("spotify_ids", [])
    status = data.get("status", "approved")
    if not spotify_ids:
        return jsonify({"success": False, "error": "Danh sách bài hát rỗng"}), 400

    count = 0
    for sid in spotify_ids:
        res = controller.db.db.tracks.update_one({"spotify_id": sid}, {"$set": {"moderation_status": status, "updated_at": datetime.utcnow()}})
        if res.modified_count > 0:
            count += 1
    return jsonify({"success": True, "updated": count, "status": status})


# ─── Headless Cookie Pool REST Endpoints ─────────────────────

@app.route("/api/cookies", methods=["GET"])
def list_cookies_endpoint():
    """Retrieve all cookies stored in the MongoDB pool."""
    cookies = controller.db.get_all_cookies()
    return jsonify({"success": True, "cookies": cookies})


@app.route("/api/cookies", methods=["POST"])
def save_cookie_endpoint():
    """Create or update a cookie document in MongoDB pool."""
    data = request.get_json() or {}
    raw_content = data.get("content", "").strip()
    if not raw_content:
        return jsonify({"success": False, "error": "Nội dung Cookie không được để trống!"}), 400

    # Parse and probe health automatically
    diag = CookieHealthChecker.check_health(raw_text=raw_content, probe_network=False)
    data["cookie_count"] = diag.get("cookie_count", 0)
    data["earliest_expiry_formatted"] = diag.get("earliest_expiry_formatted", "N/A")
    data["status"] = "valid" if diag.get("valid") else "untested"
    data["message"] = diag.get("message", "Đã lưu vào Database.")

    ok = controller.db.upsert_cookie(data)
    if ok:
        if data.get("is_active"):
            sync_active_cookie_to_disk()
        controller.log(f"🍪 Đã lưu Cookie '{data.get('name', 'Node')}' vào MongoDB pool.", level="success")
        return jsonify({"success": True, "cookie": data})
    return jsonify({"success": False, "error": "Lỗi lưu Cookie vào MongoDB"}), 500


@app.route("/api/cookies/<cookie_id>", methods=["DELETE"])
def delete_cookie_endpoint(cookie_id):
    """Delete a cookie from MongoDB pool."""
    ok = controller.db.delete_cookie(cookie_id)
    if ok:
        controller.log(f"🗑️ Đã xóa Cookie '{cookie_id}' khỏi MongoDB pool.", level="warning")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Không thể xóa Cookie"}), 404


@app.route("/api/cookies/<cookie_id>/set_active", methods=["POST"])
def set_active_cookie_endpoint(cookie_id):
    """Set cookie as the active runtime node."""
    ok = controller.db.set_active_cookie(cookie_id)
    if ok:
        sync_active_cookie_to_disk()
        c_doc = controller.db.get_cookie(cookie_id)
        c_name = c_doc.get("name", cookie_id) if c_doc else cookie_id
        controller.log(f"★ Đã chuyển Cookie chính sang: '{c_name}'", level="info")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Không thể kích hoạt Cookie"}), 400


@app.route("/api/cookies/<cookie_id>/test", methods=["POST"])
def test_cookie_endpoint(cookie_id):
    """Perform live probe test against YouTube for a specific cookie in the pool."""
    c_doc = controller.db.get_cookie(cookie_id)
    if not c_doc:
        return jsonify({"success": False, "error": "Cookie không tồn tại"}), 404

    content = c_doc.get("content", "")
    diag = CookieHealthChecker.check_health(raw_text=content, probe_network=True)
    status_label = "valid" if diag.get("valid") else "invalid"
    controller.db.update_cookie_status(
        cookie_id=cookie_id,
        status=status_label,
        latency_ms=diag.get("latency_ms", 0),
        cookie_count=diag.get("cookie_count", 0),
        earliest_expiry_formatted=diag.get("earliest_expiry_formatted", "N/A"),
        message=diag.get("message", ""),
    )
    return jsonify({
        "success": True,
        "status": status_label,
        "latency_ms": diag.get("latency_ms", 0),
        "cookie_count": diag.get("cookie_count", 0),
        "earliest_expiry_formatted": diag.get("earliest_expiry_formatted", "N/A"),
        "message": diag.get("message", ""),
        "account_logged_in": diag.get("account_logged_in", False),
    })


@app.route("/api/cookie_health", methods=["GET"])
def get_cookie_health():
    """Diagnostic endpoint to inspect active cookies.txt status."""
    probe = request.args.get("probe", "true").lower() == "true"
    health_data = CookieHealthChecker.check_health(probe_network=probe)
    return jsonify(health_data)


@socketio.on("check_cookie_status")
def handle_check_cookie_status(data=None):
    """WebSocket event to verify cookie health on-demand."""
    probe = True
    if isinstance(data, dict):
        probe = data.get("probe", True)
    health_data = CookieHealthChecker.check_health(probe_network=probe)
    emit("cookie_status_result", health_data)


# ─── Spotify App Pool REST Endpoints ─────────────────────────

@app.route("/api/spotify_apps", methods=["GET"])
def list_spotify_apps():
    """Retrieve all Spotify apps from MongoDB."""
    apps = controller.db.get_all_spotify_apps()
    return jsonify({"success": True, "apps": apps})


@app.route("/api/spotify_apps", methods=["POST"])
def save_spotify_app():
    """Create or update a Spotify app in MongoDB."""
    data = request.get_json() or {}
    ok = controller.db.upsert_spotify_app(data)
    if ok:
        active_app = controller.db.get_active_spotify_app()
        if active_app:
            settings.SPOTIFY_CLIENT_ID = active_app.get("client_id", "")
            settings.SPOTIFY_CLIENT_SECRET = active_app.get("client_secret", "")
            settings.SPOTIFY_SP_DC = active_app.get("sp_dc", "")
        return jsonify({"success": True, "app": data})
    return jsonify({"success": False, "error": "Database error saving Spotify app"}), 500


@app.route("/api/spotify_apps/<app_id>", methods=["DELETE"])
def delete_spotify_app_endpoint(app_id):
    """Delete a Spotify app from MongoDB."""
    ok = controller.db.delete_spotify_app(app_id)
    if ok:
        controller.log(f"🗑️ Deleted Spotify app '{app_id}' from pool.", level="warning")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Could not delete Spotify app"}), 404


@app.route("/api/spotify_apps/<app_id>/set_active", methods=["POST"])
def set_active_spotify_app_endpoint(app_id):
    """Set Spotify app as primary active credential."""
    ok = controller.db.set_active_spotify_app(app_id)
    if ok:
        active_app = controller.db.get_spotify_app(app_id)
        if active_app:
            settings.SPOTIFY_CLIENT_ID = active_app.get("client_id", "")
            settings.SPOTIFY_CLIENT_SECRET = active_app.get("client_secret", "")
            settings.SPOTIFY_SP_DC = active_app.get("sp_dc", "")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Could not set active Spotify app"}), 400


@app.route("/api/spotify_apps/<app_id>/test", methods=["POST"])
def test_spotify_app_endpoint(app_id):
    """Test Spotify app credentials and measure latency."""
    app_doc = controller.db.get_spotify_app(app_id)
    if not app_doc:
        return jsonify({"success": False, "error": "App not found"}), 404

    cid = app_doc.get("client_id", "").strip()
    csec = app_doc.get("client_secret", "").strip()
    is_premium = bool(app_doc.get("is_premium", False))

    start_t = time.perf_counter()
    try:
        collector = SpotifyCollector(client_id=cid, client_secret=csec)
        test_track = collector.get_track_metadata("4cOdK2wGLETKBW3PvgPWqT")
        latency = int((time.perf_counter() - start_t) * 1000)
        if test_track and test_track.get("name"):
            acc_type = "👑 Spotify Premium (320k Direct)" if is_premium else "Developer API (Client Credentials)"
            controller.db.update_spotify_app_status(
                app_id=app_id,
                status="valid",
                is_premium=is_premium,
                account_type=acc_type,
                latency_ms=latency,
            )
            return jsonify({
                "success": True,
                "status": "valid",
                "latency_ms": latency,
                "is_premium": is_premium,
                "account_type": acc_type,
            })
        else:
            raise Exception("Spotify did not return track data.")
    except Exception as ex:
        latency = int((time.perf_counter() - start_t) * 1000)
        err_msg = str(ex)
        controller.db.update_spotify_app_status(
            app_id=app_id,
            status="invalid",
            latency_ms=latency,
            error=err_msg,
        )
        return jsonify({"success": False, "status": "invalid", "latency_ms": latency, "error": err_msg})


# ─── Proxy Pool REST Endpoints ───────────────────────────────

@app.route("/api/proxies", methods=["GET"])
def list_proxies():
    """Retrieve all proxies from MongoDB."""
    proxies = controller.db.get_all_proxies()
    return jsonify({"success": True, "proxies": proxies})


@app.route("/api/proxies", methods=["POST"])
def save_proxy():
    """Create or update a proxy in MongoDB."""
    data = request.get_json() or {}
    ok = controller.db.upsert_proxy(data)
    if ok:
        controller.pm.sync_from_db()
        return jsonify({"success": True, "proxy": data})
    return jsonify({"success": False, "error": "Database error saving proxy"}), 500


@app.route("/api/proxies/<proxy_id>", methods=["DELETE"])
def delete_proxy_endpoint(proxy_id):
    """Delete a proxy from MongoDB."""
    ok = controller.db.delete_proxy(proxy_id)
    if ok:
        controller.pm.sync_from_db()
        controller.log(f"🗑️ Deleted proxy '{proxy_id}' from pool.", level="warning")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Could not delete proxy"}), 404


@app.route("/api/proxies/<proxy_id>/toggle", methods=["POST"])
def toggle_proxy_endpoint(proxy_id):
    """Toggle proxy active state."""
    data = request.get_json() or {}
    is_active = bool(data.get("is_active", True))
    ok = controller.db.toggle_proxy(proxy_id, is_active)
    if ok:
        controller.pm.sync_from_db()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Could not toggle proxy"}), 400


@app.route("/api/proxies/<proxy_id>/test", methods=["POST"])
def test_single_proxy_endpoint(proxy_id):
    """Test latency of a single proxy."""
    p_doc = controller.db.get_proxy(proxy_id)
    if not p_doc:
        return jsonify({"success": False, "error": "Proxy not found"}), 404

    url = p_doc.get("url")
    result = ProxyManager.test_proxy_connection(url)
    controller.db.update_proxy_status(
        proxy_id=proxy_id,
        status=result["status"],
        latency_ms=result["latency_ms"],
        error=result["error"],
    )
    return jsonify({"success": True, **result})


@app.route("/api/proxies/test_all", methods=["POST"])
def test_all_proxies_endpoint():
    """Ping all proxies in the pool."""
    all_p = controller.db.get_all_proxies()
    results = []
    for p in all_p:
        res = ProxyManager.test_proxy_connection(p.get("url", ""))
        controller.db.update_proxy_status(
            proxy_id=p["id"],
            status=res["status"],
            latency_ms=res["latency_ms"],
            error=res["error"],
        )
        results.append({"id": p["id"], **res})
    controller.pm.sync_from_db()
    return jsonify({"success": True, "results": results})


# ─── Network Shield, Cloudflare WARP & Egress IP Endpoints ────

@app.route("/api/network/shield_status", methods=["GET"])
def get_network_shield_status():
    """Retrieve comprehensive network shield status including host IP vs masked egress IP."""
    try:
        warp_status = WarpController.get_status()
        tailscale_status = TailscaleController.get_status()
        active_proxy = controller.pm.get_proxy()
        
        # If WARP is connected and no other proxy is explicitly chosen, use WARP SOCKS5
        test_target_proxy = active_proxy
        if not test_target_proxy and warp_status.get("is_connected"):
            test_target_proxy = WarpController.DEFAULT_PROXY_URL
        elif not test_target_proxy and tailscale_status.get("is_connected") and tailscale_status.get("active_exit_node"):
            test_target_proxy = TailscaleController.DEFAULT_PROXY_URL

        egress = ProxyManager.inspect_proxy_egress(test_target_proxy)
        direct_info = ProxyManager.inspect_proxy_egress(None)

        is_protected = bool(
            (warp_status.get("is_connected") and egress.get("success") and not egress.get("is_datacenter"))
            or (tailscale_status.get("is_connected") and egress.get("success") and not egress.get("is_datacenter"))
            or (active_proxy and egress.get("success") and not egress.get("is_datacenter"))
            or (egress.get("ip") != direct_info.get("ip") and egress.get("success"))
        )

        return jsonify({
            "success": True,
            "is_protected": is_protected,
            "host_ip": direct_info.get("ip", "Unknown"),
            "host_isp": direct_info.get("isp", "Oracle Corporation"),
            "host_country": direct_info.get("country", "SG"),
            "egress_ip": egress.get("ip", direct_info.get("ip")),
            "egress_isp": egress.get("isp", direct_info.get("isp")),
            "egress_country": egress.get("country", direct_info.get("country")),
            "latency_ms": egress.get("latency_ms", direct_info.get("latency_ms", 0)),
            "warp": warp_status,
            "tailscale": tailscale_status,
            "proxy_pool": controller.pm.get_status(),
            "rotation_strategy": controller.pm.strategy,
            "fingerprint_profile": FingerprintGenerator.PROFILES[0]["name"],
        })
    except Exception as ex:
        logger.error(f"Error fetching shield status: {ex}")
        return jsonify({"success": False, "error": str(ex)}), 500


@app.route("/api/network/warp/toggle", methods=["POST"])
def toggle_warp_endpoint():
    """Enable or disable Cloudflare WARP SOCKS5 daemon."""
    data = request.get_json() or {}
    enable = bool(data.get("enable", True))

    if enable:
        ok = WarpController.connect()
        if ok:
            # Ensure WARP is in DB proxies and enabled
            controller.db.upsert_proxy({
                "id": "proxy_cloudflare_warp",
                "name": "Cloudflare WARP Anycast SOCKS5 Gateway",
                "url": WarpController.DEFAULT_PROXY_URL,
                "protocol": "socks5",
                "is_active": True,
                "is_warp": True,
            })
            controller.pm.toggle(True)
            controller.pm.sync_from_db()
            controller.log("🛡️ Đã kết nối Cloudflare WARP SOCKS5 Gateway (127.0.0.1:40000). IP Datacenter đã được ẩn!", level="success")
            return jsonify({"success": True, "status": "CONNECTED", "warp": WarpController.get_status()})
        else:
            return jsonify({"success": False, "error": "Không thể kết nối Cloudflare WARP"}), 500
    else:
        ok = WarpController.disconnect()
        # Deactivate in db
        try:
            controller.db.update_proxy_active("proxy_cloudflare_warp", False)
        except Exception:
            pass
        controller.pm.sync_from_db()
        controller.log("⚠️ Đã ngắt kết nối Cloudflare WARP. Hệ thống đang dùng IP trực tiếp.", level="warning")
        return jsonify({"success": True, "status": "DISCONNECTED", "warp": WarpController.get_status()})


# ─── Tailscale Mesh Exit Node Endpoints ──────────────────────

@app.route("/api/network/tailscale/status", methods=["GET"])
def get_tailscale_status():
    """Retrieve detailed Tailscale status, exit nodes, and IPs."""
    status = TailscaleController.get_status()
    return jsonify({"success": True, "tailscale": status})


@app.route("/api/network/tailscale/connect", methods=["POST"])
def connect_tailscale_endpoint():
    """Authenticate and connect Tailscale using an Auth Key and SOCKS5 gateway."""
    data = request.get_json() or {}
    auth_key = data.get("auth_key", "").strip()
    exit_node = data.get("exit_node", "").strip()
    socks5_port = int(data.get("socks5_port", 1055))

    if not auth_key:
        return jsonify({"success": False, "error": "Vui lòng cung cấp Tailscale Auth Key (tskey-auth-...)"}), 400

    res = TailscaleController.connect_with_auth_key(
        auth_key=auth_key,
        exit_node=exit_node if exit_node else None,
        socks5_port=socks5_port,
    )

    if res.get("success"):
        # Auto-register Tailscale SOCKS5 proxy in DB
        proxy_url = f"socks5://127.0.0.1:{socks5_port}"
        controller.db.upsert_proxy({
            "id": "proxy_tailscale_exit_node",
            "name": f"Tailscale Mesh Exit Node ({exit_node or 'Direct Mesh'})",
            "url": proxy_url,
            "protocol": "socks5",
            "is_active": True,
            "is_tailscale": True,
        })
        controller.pm.toggle(True)
        controller.pm.sync_from_db()
        controller.log(f"💻 Đã kết nối Tailscale Mesh Network! Exit Node: {exit_node or 'Mặc định'}", level="success")
        return jsonify({"success": True, "tailscale": TailscaleController.get_status()})
    else:
        return jsonify({"success": False, "error": res.get("error")}), 500


@app.route("/api/network/tailscale/exit_node", methods=["POST"])
def set_tailscale_exit_node_endpoint():
    """Switch active Tailscale exit node."""
    data = request.get_json() or {}
    exit_node = data.get("exit_node", "").strip()
    res = TailscaleController.set_exit_node(exit_node)
    if res.get("success"):
        controller.log(f"🔄 Đã chuyển Tailscale Exit Node sang: '{exit_node or 'None'}'", level="info")
        return jsonify({"success": True, "tailscale": TailscaleController.get_status()})
    return jsonify({"success": False, "error": res.get("error")}), 500


@app.route("/api/network/tailscale/disconnect", methods=["POST"])
def disconnect_tailscale_endpoint():
    """Disconnect Tailscale."""
    ok = TailscaleController.disconnect()
    try:
        controller.db.update_proxy_active("proxy_tailscale_exit_node", False)
    except Exception:
        pass
    controller.pm.sync_from_db()
    controller.log("⚠️ Đã ngắt kết nối Tailscale Mesh Network.", level="warning")
    return jsonify({"success": True, "status": "DISCONNECTED", "tailscale": TailscaleController.get_status()})


@app.route("/api/network/strategy", methods=["POST"])
def set_network_strategy_endpoint():
    """Set proxy rotation strategy."""
    data = request.get_json() or {}
    strat = data.get("strategy", "round_robin").lower().strip()
    controller.pm.set_strategy(strat)
    
    # Save to MongoDB system_settings
    controller.db.db.system_settings.update_one(
        {"setting_id": "global_settings"},
        {"$set": {"proxy_strategy": strat}},
        upsert=True
    )
    controller.log(f"🔄 Đã cập nhật chiến lược xoay vòng Proxy: {strat.upper()}", level="info")
    return jsonify({"success": True, "strategy": strat})


@app.route("/api/network/test_egress", methods=["POST"])
def test_egress_endpoint():
    """Test egress IP via specific proxy URL."""
    data = request.get_json() or {}
    proxy_url = data.get("proxy_url")
    result = ProxyManager.inspect_proxy_egress(proxy_url)
    return jsonify(result)


# ─── User Accounts & Role Permission REST Endpoints ──────────

@app.route("/api/users", methods=["GET"])
def list_users_endpoint():
    """Retrieve all users with roles and metrics."""
    users = controller.auth.get_all_users()
    return jsonify({"success": True, "users": users})


@app.route("/api/users", methods=["POST"])
def upsert_user_endpoint():
    """Create or update a user account and role."""
    data = request.get_json() or {}
    username = data.get("username", "").strip().lower()
    if not username:
        return jsonify({"success": False, "error": "Tên đăng nhập (Username) không được để trống!"}), 400

    ok = controller.auth.upsert_user(data)
    if ok:
        role = data.get("role", "collector")
        controller.log(f"👤 Đã lưu thông tin tài khoản thành viên: @{username} (Role: {role})", level="success")
        return jsonify({"success": True, "username": username})
    return jsonify({"success": False, "error": "Không thể lưu tài khoản"}), 400


@app.route("/api/users/<username>", methods=["DELETE"])
def delete_user_endpoint(username):
    """Delete a user account."""
    if username.strip().lower() == "admin":
        return jsonify({"success": False, "error": "Không thể xóa tài khoản Quản trị viên mặc định 'admin'!"}), 400

    ok = controller.auth.admin_delete_user(username)
    if ok:
        controller.log(f"🗑️ Đã xóa tài khoản thành viên: @{username}", level="warning")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Không tìm thấy người dùng hoặc không thể xóa"}), 404


@app.route("/api/users/<username>/toggle", methods=["POST"])
def toggle_user_status_endpoint(username):
    """Toggle active status of a user."""
    data = request.get_json() or {}
    is_active = bool(data.get("is_active", True))
    ok = controller.auth.admin_toggle_user_status(username, is_active)
    if ok:
        status_str = "Kích hoạt" if is_active else "Khóa"
        controller.log(f"👤 Đã {status_str} tài khoản: @{username}", level="info")
        return jsonify({"success": True, "is_active": is_active})
    return jsonify({"success": False, "error": "Không tìm thấy người dùng"}), 404


@app.route("/api/team/leaderboard", methods=["GET"])
def get_team_leaderboard_endpoint():
    """Retrieve team leaderboard ranking."""
    leaderboard = controller.auth.get_team_leaderboard()
    return jsonify({"success": True, "leaderboard": leaderboard})


# ─── Socket Events For Admin Management & Team Profiles ──────

@socketio.on("admin_get_users")
def handle_admin_get_users():
    """Emit team members leaderboard and activity logs."""
    try:
        leaderboard = controller.auth.get_team_leaderboard()
        logs = controller.auth.get_activity_logs(limit=30)
        emit("team_data", {"users": leaderboard, "logs": logs})
    except Exception as ex:
        logger.error(f"Error handling admin_get_users: {ex}")
        emit("team_data", {"users": [], "logs": [], "error": str(ex)})


@socketio.on("admin_create_user")
def handle_admin_create_user(data):
    """Admin creates account for team member."""
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip()
    display_name = data.get("display_name", "").strip()
    role = data.get("role", "collector")

    if not username or not password:
        emit("admin_user_created", {"success": False, "error": "Vui lòng nhập đầy đủ Username và Mật khẩu!"})
        return

    user = controller.auth.create_user(username, password, email, role, display_name)
    if user:
        controller.log(f"Admin created member account: @{username} ({role})", level="success")
        emit("admin_user_created", {"success": True, "username": username})
        handle_admin_get_users()
    else:
        emit("admin_user_created", {"success": False, "error": f"Tài khoản '{username}' đã tồn tại!"})


@socketio.on("admin_reset_password")
def handle_admin_reset_password(data):
    """Admin resets a member's password."""
    username = data.get("username", "").strip()
    new_password = data.get("password", "").strip()
    ok = controller.auth.admin_reset_password(username, new_password)
    if ok:
        controller.log(f"Admin reset password for @{username}.", level="info")
        emit("admin_action_result", {"success": True, "message": f"Đã đổi mật khẩu cho @{username}!"})
    else:
        emit("admin_action_result", {"success": False, "error": "Không tìm thấy người dùng!"})


@socketio.on("admin_toggle_user_status")
def handle_admin_toggle_user_status(data):
    """Admin enables/disables a user account."""
    username = data.get("username", "").strip()
    is_active = bool(data.get("is_active", True))
    ok = controller.auth.admin_toggle_user_status(username, is_active)
    if ok:
        status_label = "Mở khóa" if is_active else "Tạm khóa"
        controller.log(f"Admin {status_label} tài khoản: @{username}", level="info")
        handle_admin_get_users()


@socketio.on("admin_delete_user")
def handle_admin_delete_user(data):
    """Admin deletes a user account."""
    username = data.get("username", "").strip()
    ok = controller.auth.admin_delete_user(username)
    if ok:
        controller.log(f"Admin deleted member account: @{username}", level="warning")
        handle_admin_get_users()


@socketio.on("get_team_profiles")
def handle_get_team_profiles():
    """Emit shared Spotify & Proxy profiles."""
    profiles = controller.auth.get_team_profiles()
    emit("team_profiles_data", profiles)


@socketio.on("save_team_profile")
def handle_save_team_profile(data):
    """Save a shared team profile."""
    ok = controller.auth.add_team_profile(data)
    if ok:
        controller.log(f"Saved shared team profile: {data.get('name')}", level="success")
        handle_get_team_profiles()


@socketio.on("delete_team_profile")
def handle_delete_team_profile(data):
    """Delete a shared team profile."""
    profile_id = data.get("profile_id")
    ok = auth_mgr.delete_team_profile(profile_id)
    if ok:
        controller.log(f"Deleted profile: {profile_id}", level="warning")
        handle_get_team_profiles()


@socketio.on("get_system_settings")
def handle_get_system_settings():
    """Emit global system settings."""
    settings_data = auth_mgr.get_system_settings()
    emit("system_settings_data", settings_data)


@socketio.on("save_system_settings")
def handle_save_system_settings(data):
    """Save global system settings and apply runtime configs."""
    ok = auth_mgr.save_system_settings(data)
    if ok:
        # Apply runtime configurations
        if "audio_bitrate" in data:
            controller.dm.bitrate = data["audio_bitrate"]
        if "download_delay" in data:
            settings.DOWNLOAD_DELAY_SECONDS = float(data["download_delay"])
        if "batch_size" in data:
            settings.BATCH_SIZE = int(data["batch_size"])
        if "cooldown_seconds" in data:
            settings.BATCH_COOLDOWN_SECONDS = int(data["cooldown_seconds"])

        controller.log("⚙️ Saved and applied system settings directly from browser!", level="success")
        emit("system_settings_saved", {"success": True})
        controller.broadcast_stats()


# ─── Live Diagnostics & In-Browser Connection Tests ───────────

@socketio.on("test_spotify_connection")
def handle_test_spotify_connection(data):
    """Test Spotify API credentials live from browser."""
    client_id = data.get("client_id", "").strip() or settings.SPOTIFY_CLIENT_ID
    client_secret = data.get("client_secret", "").strip() or settings.SPOTIFY_CLIENT_SECRET

    t0 = time.time()
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials

        auth_mgr_sp = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        sp = spotipy.Spotify(auth_manager=auth_mgr_sp, requests_timeout=8)
        res = sp.search(q="Vũ.", type="artist", limit=1)
        latency_ms = int((time.time() - t0) * 1000)

        artists = res.get("artists", {}).get("items", [])
        if artists:
            artist_name = artists[0].get("name")
            controller.log(f"🟢 Spotify API Test SUCCESS: Connected in {latency_ms}ms (Sample: {artist_name})", level="success")
            emit("test_spotify_result", {
                "success": True,
                "latency_ms": latency_ms,
                "message": f"Kết nối Spotify thành công ({latency_ms}ms) — Tìm thấy nghệ sĩ: '{artist_name}'",
            })
        else:
            emit("test_spotify_result", {"success": False, "message": "Spotify API phản hồi rỗng!"})
    except Exception as ex:
        controller.log(f"🔴 Spotify API Test FAILED: {ex}", level="error")
        emit("test_spotify_result", {"success": False, "message": f"Lỗi kết nối Spotify: {str(ex)}"})


@socketio.on("test_proxy_connection")
def handle_test_proxy_connection(data):
    """Test Proxy connectivity live from browser."""
    proxy_url = data.get("proxy_url", "").strip()
    if not proxy_url:
        emit("test_proxy_result", {"success": False, "message": "Vui lòng nhập URL Proxy cần kiểm tra!"})
        return

    t0 = time.time()
    try:
        import requests
        proxies = {"http": proxy_url, "https": proxy_url}
        resp = requests.get("https://www.google.com", proxies=proxies, timeout=8)
        latency_ms = int((time.time() - t0) * 1000)

        if resp.status_code == 200:
            controller.log(f"🟢 Proxy Test SUCCESS: {proxy_url} ({latency_ms}ms)", level="success")
            emit("test_proxy_result", {
                "success": True,
                "latency_ms": latency_ms,
                "message": f"Proxy hoạt động tốt ({latency_ms}ms, HTTP 200 OK)",
            })
        else:
            emit("test_proxy_result", {"success": False, "message": f"Proxy phản hồi HTTP {resp.status_code}"})
    except Exception as ex:
        controller.log(f"🔴 Proxy Test FAILED: {proxy_url} -> {ex}", level="error")
        emit("test_proxy_result", {"success": False, "message": f"Lỗi kết nối qua Proxy: {str(ex)}"})


@socketio.on("test_ytdlp_extraction")
def handle_test_ytdlp_extraction(data):
    """Test yt-dlp metadata extraction live without downloading."""
    test_query = data.get("query", "Son Tung M-TP Chung Ta Cua Tuong Lai").strip()
    t0 = time.time()
    try:
        import yt_dlp
        ydl_opts = {
            "extract_flat": False,
            "quiet": True,
            "no_warnings": True,
            "default_search": "ytsearch1:",
        }
        if controller.dm.cookies_path and controller.dm.cookies_path.exists():
            ydl_opts["cookiefile"] = str(controller.dm.cookies_path)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{test_query}", download=False)
            latency_ms = int((time.time() - t0) * 1000)

            entries = info.get("entries", [])
            if entries:
                track = entries[0]
                title = track.get("title")
                uploader = track.get("uploader")
                duration = track.get("duration", 0)
                controller.log(f"🟢 yt-dlp Extraction Test SUCCESS in {latency_ms}ms: '{title}'", level="success")
                emit("test_ytdlp_result", {
                    "success": True,
                    "latency_ms": latency_ms,
                    "title": title,
                    "uploader": uploader,
                    "duration": duration,
                    "message": f"Trích xuất thành công trong {latency_ms}ms: '{title}' ({int(duration)}s)",
                })
            else:
                emit("test_ytdlp_result", {"success": False, "message": "Không tìm thấy kết quả phù hợp trên YouTube!"})
    except Exception as ex:
        controller.log(f"🔴 yt-dlp Extraction Test FAILED: {ex}", level="error")
        emit("test_ytdlp_result", {"success": False, "message": f"Lỗi trích xuất yt-dlp: {str(ex)}"})


@socketio.on("upload_cookie_text")
def handle_upload_cookie_text(data):
    """Save raw cookie text pasted via web UI."""
    cookie_text = data.get("cookie_text", "").strip()
    if cookie_text:
        target_path = settings.CONFIG_DIR / "cookies.txt"
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(cookie_text)
        settings.COOKIES_FILE = target_path
        controller.dm.cookies_path = target_path
        controller.log("🍪 Saved and applied cookies.txt to active server session.", level="success")
        emit("cookie_saved", {"success": True, "size": len(cookie_text)})


# ─── Operational Sockets ─────────────────────────────────────

@socketio.on("import_selected_tracks")
def handle_import_selected_tracks(data):
    """Import selected tracks from preview studio into DB."""
    selected_tracks = data.get("tracks", [])
    operator = data.get("operator") or session.get("user", {}).get("username", "admin")

    if not selected_tracks:
        controller.log("No tracks selected for import.", level="warning")
        return

    controller.log(f"📥 Importing {len(selected_tracks)} selected tracks into MongoDB (by @{operator})...")

    def _import_worker():
        try:
            collector = SpotifyCollector()
            existing_db_tracks = controller.db.get_all_tracks()
            unique_new, updated_existing, skipped_dups = Deduplicator.dedup_tracks(
                tracks=selected_tracks,
                existing_db_tracks=existing_db_tracks,
            )

            all_active_tracks = unique_new + updated_existing
            for t in all_active_tracks:
                if not t.get("added_by"):
                    t["added_by"] = operator
                if not t.get("ingest_type"):
                    t["ingest_type"] = "metadata_only"

            artists_map = collector.collect_artists_info([t.get("artist_spotify_id") for t in all_active_tracks], tracks=all_active_tracks)
            albums_map = collector.collect_albums_info([t.get("album_spotify_id") for t in all_active_tracks], tracks=all_active_tracks)

            if artists_map:
                controller.db.bulk_upsert_artists(list(artists_map.values()))
            if albums_map:
                controller.db.bulk_upsert_albums(list(albums_map.values()))
            if unique_new:
                controller.db.bulk_upsert_tracks(unique_new)
            if updated_existing:
                controller.db.bulk_upsert_tracks(updated_existing)

            auth_mgr.record_user_action(
                username=operator,
                action_type="crawl_metadata",
                count=len(unique_new),
                details=f"Imported {len(unique_new)} new tracks from Preview Studio",
            )

            controller.log(
                f"✅ Successfully imported {len(unique_new)} new tracks ({len(updated_existing)} updated, {len(skipped_dups)} skipped dups) by @{operator}!",
                level="success",
            )
            socketio.emit("import_success", {
                "new_count": len(unique_new),
                "updated_count": len(updated_existing),
                "total_imported": len(selected_tracks),
            })
            controller.broadcast_stats()
        except Exception as ex:
            controller.log(f"Import failed: {ex}", level="error")

    threading.Thread(target=_import_worker, daemon=True).start()


@socketio.on("start_crawl")
def handle_start_crawl(data):
    mode = data.get("mode", "curated")
    query = data.get("query", "")
    genre = data.get("genre", None)
    limit = int(data.get("limit", 50))
    operator = data.get("operator") or session.get("user", {}).get("username", "admin")
    controller.start_crawl_task(mode=mode, query=query, genre=genre, limit_per_playlist=limit, operator_name=operator)


@socketio.on("start_download")
def handle_start_download(data):
    limit = int(data.get("limit", 50))
    delay = float(data.get("delay", 3.0))
    retry_failed = bool(data.get("retry_failed", False))
    specific_ids = data.get("specific_ids", None)
    operator = data.get("operator") or session.get("user", {}).get("username", "admin")
    controller.start_download_task(
        limit=limit,
        delay=delay,
        retry_failed=retry_failed,
        operator_name=operator,
        specific_ids=specific_ids,
    )


@socketio.on("pause_pipeline")
def handle_pause_pipeline():
    controller.pause()


@socketio.on("stop_pipeline")
def handle_stop_pipeline():
    controller.stop()


@socketio.on("toggle_proxy")
def handle_toggle_proxy(data):
    enable = bool(data.get("enable", False))
    controller.toggle_proxy(enable)


@socketio.on("export_data")
def handle_export_data():
    exporter = ExportManager(db_manager=controller.db)
    exporter.generate_playlists()
    exporter.export_all_json()
    exporter.export_sql_seed()
    exporter.generate_report()
    controller.log("Exported JSON, SQL, and Markdown reports successfully!", level="success")
    controller.broadcast_stats()


def main():
    logger.info(f"Starting Web Dashboard at http://{settings.DASHBOARD_HOST}:{settings.DASHBOARD_PORT}")
    socketio.run(
        app,
        host=settings.DASHBOARD_HOST,
        port=settings.DASHBOARD_PORT,
        debug=settings.DASHBOARD_DEBUG,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()

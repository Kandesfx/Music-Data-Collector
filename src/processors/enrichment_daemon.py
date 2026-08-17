"""
Music Data Collector - Background Auto-Enrichment Daemon
Utilizes idle server CPU and RAM to autonomously inspect and enrich downloaded music data:
1. Calculates missing Audio Features (BPM, Key, Loudness, Waveform Peaks)
2. Fetches missing Lyrics (Synced .lrc & Plain) from LRCLIB
3. Upgrades missing Cover Art to HD
4. Broadcasts enrichment telemetry to the Studio Dashboard
"""

import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List

from config import settings
from src.storage.db_manager import DBManager
from src.collectors.lyrics_collector import LyricsCollector
from src.processors.audio_feature_extractor import AudioFeatureExtractor
from src.processors.audio_verifier import AudioVerifier
from src.processors.post_processor import PostProcessor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AutoEnrichmentDaemon:
    """Autonomous background worker that enhances database metadata and audio features."""

    def __init__(self, db_manager: Optional[DBManager] = None, interval_sec: int = 60):
        self.db = db_manager or DBManager()
        self.interval_sec = interval_sec
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Telemetry
        self.total_features_computed = 0
        self.total_lyrics_enriched = 0
        self.last_run_timestamp: Optional[str] = None
        self.current_task_status = "Idle"

    def start(self):
        """Start the background enrichment daemon."""
        if self.is_running:
            return

        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="EnrichmentDaemonThread")
        self._thread.start()
        logger.info("🤖 AutoEnrichmentDaemon background service started.")

    def stop(self):
        """Stop the background daemon gracefully."""
        self.is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("⏹️ AutoEnrichmentDaemon stopped.")

    def _run_loop(self):
        """Main periodic loop."""
        time.sleep(10)  # Initial wait before starting first pass
        while not self._stop_event.is_set():
            try:
                self._enrich_audio_features_pass()
                self._enrich_lyrics_pass()
                self._enrich_moderation_pass()
                self.last_run_timestamp = time.strftime("%H:%M:%S %d/%m/%Y")
            except Exception as e:
                logger.error(f"Error in AutoEnrichmentDaemon loop: {e}")

            # Sleep interval with interruptible check
            self.current_task_status = "Sleeping"
            self._stop_event.wait(timeout=self.interval_sec)

    def trigger_pass_now(self) -> Dict[str, Any]:
        """Manually trigger an immediate enrichment pass in a separate thread."""
        threading.Thread(target=self._run_enrichment_sync, daemon=True).start()
        return {"success": True, "message": "Enrichment pass triggered successfully"}

    def _run_enrichment_sync(self):
        try:
            self._enrich_audio_features_pass()
            self._enrich_lyrics_pass()
            self._enrich_moderation_pass()
            self.last_run_timestamp = time.strftime("%H:%M:%S %d/%m/%Y")
        except Exception as e:
            logger.error(f"Manual enrichment pass failed: {e}")

    def _enrich_audio_features_pass(self):
        """Scan DB for completed tracks that lack audio features and analyze them."""
        if not self.db.is_connected():
            return

        # Find completed tracks without audio_features
        tracks = list(self.db.db["tracks"].find({
            "download_status": "completed",
            "audio_features": {"$exists": False}
        }).limit(20))

        if not tracks:
            return

        self.current_task_status = f"Analyzing Audio Features ({len(tracks)} tracks)"
        logger.info(f"🤖 [Enrichment] Found {len(tracks)} tracks needing audio feature extraction...")

        for track in tracks:
            if self._stop_event.is_set():
                break

            sp_id = track.get("spotify_id")
            rel_path = track.get("local_path")
            if not rel_path:
                continue

            full_path = settings.BASE_DIR / rel_path
            if not full_path.exists():
                continue

            try:
                features = AudioFeatureExtractor.analyze_track(full_path, spotify_id=sp_id)
                if features.get("success"):
                    self.db.db["tracks"].update_one(
                        {"spotify_id": sp_id},
                        {"$set": {"audio_features": features}}
                    )
                    self.total_features_computed += 1
                    logger.info(f"✨ [Enrichment] Extracted features for {track.get('artist_name')} - {track.get('name')}: BPM={features.get('bpm')}, Key={features.get('key_signature')}")
            except Exception as e:
                logger.debug(f"Failed to extract features for {sp_id}: {e}")

    def _enrich_lyrics_pass(self):
        """Scan DB for tracks lacking synced or plain lyrics and fetch from LRCLIB."""
        if not self.db.is_connected():
            return

        # Find tracks without lyrics
        tracks = list(self.db.db["tracks"].find({
            "download_status": "completed",
            "lyrics_synced": {"$in": [None, ""]},
            "lyrics_plain": {"$in": [None, ""]}
        }).limit(15))

        if not tracks:
            return

        self.current_task_status = f"Fetching Lyrics ({len(tracks)} tracks)"

        for track in tracks:
            if self._stop_event.is_set():
                break

            sp_id = track.get("spotify_id")
            title = track.get("name", "")
            artist = track.get("artist_name", "")
            album = track.get("album_name", "")
            duration_ms = track.get("duration_ms")
            rel_path = track.get("local_path")

            try:
                lyr_data = LyricsCollector.fetch_lyrics(
                    track_name=title,
                    artist_name=artist,
                    album_name=album,
                    duration_ms=duration_ms,
                )
                if lyr_data:
                    plain_l = lyr_data.get("plain_lyrics")
                    synced_l = lyr_data.get("synced_lyrics")
                    rel_lrc_path = None

                    if rel_path and synced_l:
                        full_path = settings.BASE_DIR / rel_path
                        if full_path.exists():
                            lrc_p = PostProcessor.save_synced_lyrics(full_path, synced_l)
                            if lrc_p:
                                try:
                                    rel_lrc_path = str(lrc_p.resolve().relative_to(settings.BASE_DIR.resolve())).replace("\\", "/")
                                except Exception:
                                    rel_lrc_path = str(lrc_p).replace("\\", "/")

                    self.db.db["tracks"].update_one(
                        {"spotify_id": sp_id},
                        {"$set": {
                            "lyrics_plain": plain_l,
                            "lyrics_synced": synced_l,
                            "lrc_path": rel_lrc_path,
                        }}
                    )
                    self.total_lyrics_enriched += 1
                    logger.info(f"📝 [Enrichment] Found & saved lyrics for {artist} - {title}!")
            except Exception as e:
                logger.debug(f"Failed to fetch lyrics for {sp_id}: {e}")

    def _enrich_moderation_pass(self):
        """Scan DB for completed tracks lacking moderation reports and evaluate them."""
        if not self.db.is_connected():
            return

        tracks = list(self.db.db["tracks"].find({
            "download_status": "completed",
            "moderation_score": {"$exists": False}
        }).limit(25))

        if not tracks:
            return

        self.current_task_status = f"Running AI Audio Moderation ({len(tracks)} tracks)"

        for track in tracks:
            if self._stop_event.is_set():
                break

            sp_id = track.get("spotify_id")
            rel_path = track.get("local_path")
            if not rel_path:
                continue

            full_path = settings.BASE_DIR / rel_path
            if not full_path.exists():
                continue

            try:
                report = AudioVerifier.evaluate_track(track, full_path)
                if report.get("success"):
                    self.db.db["tracks"].update_one(
                        {"spotify_id": sp_id},
                        {
                            "$set": {
                                "moderation_status": report["status"],
                                "moderation_score": report["score"],
                                "moderation_report": report,
                            }
                        }
                    )
                    logger.info(f"🛡️ [Enrichment Moderation] {track.get('artist_name')} - {track.get('name')}: {report['score']}/100 ({report['status'].upper()})")
            except Exception as e:
                logger.debug(f"Failed moderation pass for {sp_id}: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Return operational status and statistics."""
        return {
            "is_running": self.is_running,
            "status": self.current_task_status,
            "interval_sec": self.interval_sec,
            "total_features_computed": self.total_features_computed,
            "total_lyrics_enriched": self.total_lyrics_enriched,
            "last_run": self.last_run_timestamp or "Chưa chạy",
        }


# Global Singleton Daemon
enrichment_daemon = AutoEnrichmentDaemon(interval_sec=60)

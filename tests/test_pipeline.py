"""
Unit Tests for Music Data Collector Core Modules (Pipeline v3)
Tests: DataCleaner, GenreMapper, Deduplicator, HealthChecker, ProxyManager, SessionManager,
       YTMusicMatcher, LyricsCollector, PostProcessor.
"""

import sys
import unittest
from pathlib import Path
import tempfile
import os
import time

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.processors.data_cleaner import DataCleaner
from src.processors.genre_mapper import GenreMapper
from src.processors.deduplicator import Deduplicator
from src.processors.post_processor import PostProcessor
from src.downloaders.ytmusic_matcher import YTMusicMatcher
from src.collectors.lyrics_collector import LyricsCollector
from src.utils.health_checker import HealthChecker
from src.utils.proxy_manager import ProxyManager
from src.utils.session_manager import SessionManager


class TestDataCleaner(unittest.TestCase):
    def test_clean_text(self):
        raw = "  Hello  World \n"
        self.assertEqual(DataCleaner.clean_text(raw), "Hello  World")

    def test_clean_song_title(self):
        title = "See You Again (Official Music Video) [Audio] feat. Charlie Puth"
        cleaned = DataCleaner.clean_song_title(title)
        self.assertEqual(cleaned, "See You Again feat. Charlie Puth")

    def test_slugify(self):
        title = "Đường Tôi Chở Em Về (Acoustic)"
        slug = DataCleaner.slugify(title)
        self.assertTrue("duong-toi-cho-em-ve" in slug or "duong" in slug)


class TestGenreMapper(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(GenreMapper.map_genre("vietnamese pop"), "vpop")
        self.assertEqual(GenreMapper.map_genre("dance pop"), "pop")
        self.assertEqual(GenreMapper.map_genre("heavy metal"), "metal")
        self.assertEqual(GenreMapper.map_genre("lo-fi beats"), "ambient")
        self.assertEqual(GenreMapper.map_genre("unknown_genre_xyz"), "other")

    def test_map_genres_list(self):
        raw = ["dance pop", "electropop", "vietnamese indie"]
        mapped = GenreMapper.map_genres(raw)
        self.assertIn("pop", mapped)
        self.assertIn("vpop", mapped)


class TestDeduplicator(unittest.TestCase):
    def test_dedup_batch(self):
        tracks = [
            {"spotify_id": "id1", "name": "Song A", "artist_name": "Artist 1", "genres": ["vpop"]},
            {"spotify_id": "id1", "name": "Song A (Duplicate ID)", "artist_name": "Artist 1", "genres": ["pop"]},
            {"spotify_id": "id2", "name": "Song A (Official Audio)", "artist_name": "Artist 1", "genres": ["indie"]},  # Duplicate name + artist
            {"spotify_id": "id3", "name": "Song B", "artist_name": "Artist 2", "genres": ["rock"]},
        ]
        unique, updated, dups = Deduplicator.dedup_tracks(tracks)
        self.assertEqual(len(unique), 2)  # Song A and Song B
        self.assertEqual(len(dups), 2)    # 2 duplicates skipped
        
        # Check genre merging
        song_a = next(t for t in unique if t["name"] == "Song A")
        self.assertIn("vpop", song_a["genres"])
        self.assertIn("pop", song_a["genres"])
        self.assertIn("indie", song_a["genres"])

    def test_fuzzy_match(self):
        t1 = {"spotify_id": "a1", "name": "Chúng Ta Của Hiện Tại", "artist_name": "Sơn Tùng M-TP", "duration_ms": 300000}
        t2 = {"spotify_id": "a2", "name": "Chúng Ta Của Hiện Tại (Audio)", "artist_name": "Sơn Tùng M-TP", "duration_ms": 301000}
        self.assertTrue(Deduplicator.fuzzy_match_tracks(t1, t2))


class TestYTMusicMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = YTMusicMatcher()

    def test_normalize_string(self):
        norm = self.matcher._normalize_string("Espresso (Official Video) [Remastered]")
        self.assertEqual(norm, "espresso")

    def test_parse_duration_seconds(self):
        self.assertEqual(self.matcher._parse_duration_seconds("3:45"), 225)
        self.assertEqual(self.matcher._parse_duration_seconds("1:02:15"), 3735)
        self.assertIsNone(self.matcher._parse_duration_seconds(None))

    def test_calculate_match_score(self):
        candidate = {
            "title": "Babydoll",
            "artists": [{"name": "Dominic Fike"}],
            "duration": "1:38",
            "resultType": "song",
        }
        score = self.matcher._calculate_match_score(
            candidate=candidate,
            target_artist="Dominic Fike",
            target_title="Babydoll",
            target_duration_sec=98,  # 1m38s
        )
        self.assertGreaterEqual(score, 80.0)


class TestLyricsCollector(unittest.TestCase):
    def test_fetch_lyrics(self):
        lyrics = LyricsCollector.fetch_lyrics(
            track_name="Babydoll",
            artist_name="Dominic Fike",
            duration_ms=98000,
        )
        self.assertIsNotNone(lyrics)
        self.assertTrue(lyrics.get("has_synced"))
        self.assertIn("babydoll", lyrics.get("synced_lyrics", "").lower())


class TestPostProcessor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audio_path = Path(self.temp_dir.name) / "test_song.mp3"
        self.audio_path.touch()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_synced_lyrics(self):
        lrc_content = "[00:10.00] Hello World\n[00:15.00] Second Line"
        lrc_path = PostProcessor.save_synced_lyrics(self.audio_path, lrc_content)
        self.assertIsNotNone(lrc_path)
        self.assertTrue(lrc_path.exists())
        self.assertEqual(lrc_path.suffix, ".lrc")
        self.assertEqual(lrc_path.read_text(encoding="utf-8"), lrc_content)


class TestHealthChecker(unittest.TestCase):
    def test_auto_pause(self):
        checker = HealthChecker(fail_threshold=3, window_size=5, max_pauses=2, pause_seconds=10)
        checker.record(False)
        checker.record(False)
        self.assertFalse(checker.should_pause())
        checker.record(False)
        self.assertTrue(checker.should_pause())
        self.assertFalse(checker.should_stop())

        checker.trigger_pause()
        checker.trigger_pause()
        self.assertTrue(checker.should_stop())


class TestProxyManager(unittest.TestCase):
    def test_proxy_rotation(self):
        proxies = ["socks5://1.1.1.1:1080", "socks5://2.2.2.2:1080"]
        pm = ProxyManager(proxy_list=proxies, enabled=True, strategy="round_robin")
        self.assertEqual(pm.get_proxy(), "socks5://1.1.1.1:1080")
        self.assertEqual(pm.get_proxy(), "socks5://2.2.2.2:1080")
        self.assertEqual(pm.get_proxy(), "socks5://1.1.1.1:1080")

        pm.toggle(False)
        self.assertIsNone(pm.get_proxy())


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_session.db"
        self.sm = SessionManager(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_session_lifecycle(self):
        sid = self.sm.start_session(total_tracks=10)
        self.assertIsInstance(sid, int)

        self.sm.checkpoint(sid, "spotify_01", "completed", method="ytmusic_precision", file_path="audio/song1.mp3")
        self.sm.checkpoint(sid, "spotify_02", "failed", method="ytdlp", error="Network Error")

        completed_ids = self.sm.get_completed_spotify_ids()
        self.assertIn("spotify_01", completed_ids)
        self.assertNotIn("spotify_02", completed_ids)

        stats = self.sm.get_session_stats()
        self.assertEqual(stats["total_checkpoints"], 2)
        self.assertEqual(stats["completed_checkpoints"], 1)
        self.assertEqual(stats["failed_checkpoints"], 1)

        self.sm.end_session(sid, status="completed")


class TestAuthManager(unittest.TestCase):
    def test_password_hash_and_verify(self):
        from src.storage.auth_manager import AuthManager
        pwd = "SecretPassword123!"
        hashed = AuthManager.hash_password(pwd)
        self.assertNotEqual(pwd, hashed)
        self.assertTrue(AuthManager.verify_password(hashed, pwd))
        self.assertFalse(AuthManager.verify_password(hashed, "WrongPassword"))

    def test_system_settings_persistence(self):
        from src.storage.auth_manager import AuthManager
        auth_mgr = AuthManager()
        settings_data = auth_mgr.get_system_settings()
        self.assertIn("audio_bitrate", settings_data)

        updated = auth_mgr.save_system_settings({"audio_bitrate": "320k", "download_delay": 4.0})
        self.assertTrue(updated)
        refreshed = auth_mgr.get_system_settings()
        self.assertEqual(refreshed.get("download_delay"), 4.0)


class TestCatalogManagement(unittest.TestCase):
    def setUp(self):
        from src.storage.db_manager import DBManager
        self.db = DBManager()
        self.test_id = f"test_track_catalog_{int(time.time()*1000)}"
        self.test_track = {
            "spotify_id": self.test_id,
            "name": "Bài Hát Test Catalog",
            "artist_name": "Nghệ Sĩ Test",
            "album_name": "Album Test",
            "genres": ["vpop"],
            "duration_ms": 180000,
            "popularity": 75,
            "download_status": "completed",
            "moderation_status": "pending",
        }
        self.db.upsert_track(self.test_track)

    def tearDown(self):
        self.db.delete_track(self.test_id, delete_audio_file=False)

    def test_paginated_query_and_search(self):
        res = self.db.get_paginated_tracks(page=1, limit=10, search="Bài Hát Test Catalog")
        self.assertGreaterEqual(res["total_items"], 1)
        found = any(t["spotify_id"] == self.test_id for t in res["items"])
        self.assertTrue(found)

    def test_update_and_moderation(self):
        # Update metadata
        ok = self.db.update_track_metadata(self.test_id, {"name": "Tên Đã Cập Nhật", "popularity": 90})
        self.assertTrue(ok)

        # Set moderation
        mod_ok = self.db.set_moderation_status(self.test_id, "approved", reviewer="admin")
        self.assertTrue(mod_ok)

        updated_track = self.db.get_track(self.test_id)
        self.assertEqual(updated_track["name"], "Tên Đã Cập Nhật")
        self.assertEqual(updated_track["popularity"], 90)
        self.assertEqual(updated_track["moderation_status"], "approved")
        self.assertEqual(updated_track["moderated_by"], "admin")


if __name__ == "__main__":
    unittest.main()


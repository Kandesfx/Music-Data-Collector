import os
import sys
from pathlib import Path

# Add project root
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import yt_dlp
from src.downloaders.download_manager import DownloadManager
from src.storage.db_manager import DBManager
from src.storage.file_manager import FileManager
from src.utils.session_manager import SessionManager
from src.utils.proxy_manager import ProxyManager
from src.utils.health_checker import HealthChecker
from src.utils.cookie_checker import CookieHealthChecker
from src.utils.fingerprints import FingerprintGenerator

print("=== 1. Checking Cookie Health on Server ===")
health = CookieHealthChecker.check_health(probe_network=True)
print("Cookie Health Result:", health)

print("\n=== 2. Inspecting Active Fingerprint & Client Args ===")
fp = FingerprintGenerator.get_active_profile()
print("Active Fingerprint:", fp.get("name") if fp else "None")
print("Extractor Args:", FingerprintGenerator.get_ytdlp_extractor_args())
print("HTTP Headers:", FingerprintGenerator.get_ytdlp_http_headers())

print("\n=== 3. Testing Direct yt-dlp Download ===")
db = DBManager()
fm = FileManager()
sm = SessionManager()
pm = ProxyManager(db_manager=db)
hc = HealthChecker()
dm = DownloadManager(db, fm, sm, hc, pm)

# Pick a track
tracks = db.get_pending_tracks(limit=1)
track = tracks[0] if tracks else {"spotify_id": "test_diagnose_1", "name": "Con Mua Ngang Qua", "artist_name": "Son Tung M-TP"}
print(f"Target Track: '{track.get('name')}' by '{track.get('artist_name')}'")

ok, file_path, method = dm.download_track(track)
print(f"Download Result: success={ok}, method={method}, path={file_path}")

# Check latest track status in DB
if track.get("spotify_id"):
    db_track = db.get_track(track["spotify_id"])
    print("DB Track Download Status:", db_track.get("download_status") if db_track else "None")
    print("DB Track Error:", db_track.get("error_message") if db_track else "None")

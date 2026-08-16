"""
Music Data Collector - Settings Module v2
Central configuration loaded from environment variables and config files.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# ─── Base Directories ────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(__file__).resolve().parent

# Try loading .env from config/ first, then project root
env_path = CONFIG_DIR / ".env"
if not env_path.exists():
    env_path = BASE_DIR / ".env"
load_dotenv(env_path)

# ─── Spotify API Settings ────────────────────────────────────
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:9900/")
SPOTIFY_ENABLED = bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)

# ─── YouTube / Cookies Settings ──────────────────────────────
COOKIES_FROM_BROWSER = os.getenv("COOKIES_FROM_BROWSER", "").strip().lower()  # e.g. "chrome", "edge", "firefox"
YOUTUBE_COOKIES_PATH = Path(os.getenv("YOUTUBE_COOKIES_PATH", CONFIG_DIR / "cookies.txt"))

# ─── Database Configuration ──────────────────────────────────
DB_ENGINE = os.getenv("DB_ENGINE", "mongodb").lower()

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "music_streaming")

# PostgreSQL
PG_CONFIG = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "user": os.getenv("PG_USER", "postgres"),
    "password": os.getenv("PG_PASSWORD", ""),
    "database": os.getenv("PG_DATABASE", "music_streaming"),
}

# ─── File Paths ──────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
AUDIO_DIR = Path(os.getenv("AUDIO_DIR", DATA_DIR / "audio"))
IMAGES_DIR = Path(os.getenv("IMAGES_DIR", DATA_DIR / "images"))
RAW_DIR = Path(os.getenv("RAW_DIR", DATA_DIR / "raw"))
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", DATA_DIR / "exports"))
LOG_DIR = Path(os.getenv("LOG_DIR", BASE_DIR / "logs"))
SESSION_DB_PATH = Path(os.getenv("SESSION_DB_PATH", DATA_DIR / "session.db"))

# Ensure all directories exist
for directory in [DATA_DIR, AUDIO_DIR, IMAGES_DIR, RAW_DIR, EXPORT_DIR, LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ─── Download & Rate Limiting Settings ────────────────────────
SPOTDL_THREADS = int(os.getenv("SPOTDL_THREADS", "1"))
SPOTDL_BITRATE = os.getenv("SPOTDL_BITRATE", "192k")
DOWNLOAD_DELAY_SECONDS = float(os.getenv("DOWNLOAD_DELAY_SECONDS", "2.0"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
BATCH_COOLDOWN_SECONDS = int(os.getenv("BATCH_COOLDOWN_SECONDS", "120"))
MAX_DOWNLOAD_RETRIES = int(os.getenv("MAX_DOWNLOAD_RETRIES", "2"))

# Audio File Validation Constraints
AUDIO_VALIDATION = {
    "min_size_bytes": 100_000,      # > 100KB
    "max_size_bytes": 50_000_000,   # < 50MB
    "allowed_formats": [".mp3"],
    "min_duration_sec": 30,
    "max_duration_sec": 3600,       # 60 minutes
}

# ─── Health Checker & Resilience ──────────────────────────────
HEALTH_FAIL_THRESHOLD = int(os.getenv("HEALTH_FAIL_THRESHOLD", "5"))
HEALTH_WINDOW_SIZE = int(os.getenv("HEALTH_WINDOW_SIZE", "10"))
HEALTH_MAX_PAUSES = int(os.getenv("HEALTH_MAX_PAUSES", "3"))
HEALTH_PAUSE_SECONDS = int(os.getenv("HEALTH_PAUSE_SECONDS", "600"))

# ─── Proxy Settings (Optional Toggle) ─────────────────────────
PROXY_ENABLED = os.getenv("PROXY_ENABLED", "false").lower() in ("true", "1", "yes")
_raw_proxies = os.getenv("PROXY_LIST", "")
PROXY_LIST = [p.strip() for p in _raw_proxies.split(",") if p.strip()]
PROXY_ROTATION = os.getenv("PROXY_ROTATION", "round_robin").lower()

# ─── Dashboard Settings ───────────────────────────────────────
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))
DASHBOARD_DEBUG = os.getenv("DASHBOARD_DEBUG", "false").lower() in ("true", "1", "yes")

# ─── Load Playlists Config ───────────────────────────────────
def load_playlists_config():
    """Load playlist configuration from playlists.json."""
    playlists_file = CONFIG_DIR / "playlists.json"
    if playlists_file.exists():
        with open(playlists_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"playlists": []}

PLAYLISTS_CONFIG = load_playlists_config()

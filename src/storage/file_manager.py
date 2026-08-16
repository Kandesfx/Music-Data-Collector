"""
Music Data Collector - File Manager Module
Organizes local folder structures, audio paths, and filesystem utilities.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from config import settings
from src.processors.data_cleaner import DataCleaner
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FileManager:
    """Manages audio/image directories and file naming conventions."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or settings.DATA_DIR
        self.audio_dir = settings.AUDIO_DIR
        self.images_dir = settings.IMAGES_DIR
        self.raw_dir = settings.RAW_DIR
        self.export_dir = settings.EXPORT_DIR
        self.log_dir = settings.LOG_DIR
        self.ensure_directories()

    def ensure_directories(self):
        """Create necessary subdirectories."""
        for d in [
            self.data_dir,
            self.audio_dir,
            self.images_dir,
            self.images_dir / "artists",
            self.images_dir / "albums",
            self.raw_dir,
            self.export_dir,
            self.log_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def get_audio_path(self, artist_name: str, spotify_id: str, title: str) -> Path:
        """
        Generate standardized audio destination path:
        data/audio/<artist_slug>/<spotify_id>_<title_slug>.mp3
        """
        artist_slug = DataCleaner.slugify(artist_name, max_length=40)
        title_slug = DataCleaner.slugify(title, max_length=50)
        artist_folder = self.audio_dir / artist_slug
        artist_folder.mkdir(parents=True, exist_ok=True)
        return artist_folder / f"{spotify_id}_{title_slug}.mp3"

    def get_artist_image_path(self, spotify_id: str) -> Path:
        """Destination for artist avatar image."""
        return self.images_dir / "artists" / f"{spotify_id}.jpg"

    def get_album_image_path(self, spotify_id: str) -> Path:
        """Destination for album cover art."""
        return self.images_dir / "albums" / f"{spotify_id}.jpg"

    def get_file_size(self, path: Path) -> int:
        """Return file size in bytes if file exists."""
        try:
            return path.stat().st_size if path.exists() else 0
        except Exception:
            return 0

    def file_exists(self, path: Path) -> bool:
        """Check if path exists and has size > 0."""
        try:
            return path.exists() and path.stat().st_size > 0
        except Exception:
            return False

    def move_file(self, src: Path, dest: Path) -> Path:
        """Move or rename file safely."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        return Path(shutil.move(str(src), str(dest)))

    def copy_file(self, src: Path, dest: Path) -> Path:
        """Copy file safely."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        return Path(shutil.copy2(str(src), str(dest)))

    def remove_file(self, path: Path):
        """Safely delete a file."""
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete {path}: {e}")

    def get_storage_stats(self) -> Dict[str, Any]:
        """Compute disk usage statistics for stored audio and images."""
        audio_files = list(self.audio_dir.glob("**/*.mp3"))
        total_audio_bytes = sum(self.get_file_size(f) for f in audio_files)

        image_files = list(self.images_dir.glob("**/*.*"))
        total_image_bytes = sum(self.get_file_size(f) for f in image_files)

        return {
            "total_audio_files": len(audio_files),
            "total_audio_size_mb": round(total_audio_bytes / (1024 * 1024), 2),
            "total_image_files": len(image_files),
            "total_image_size_mb": round(total_image_bytes / (1024 * 1024), 2),
            "audio_dir": str(self.audio_dir),
            "images_dir": str(self.images_dir),
        }

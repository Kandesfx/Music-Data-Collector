"""
Music Data Collector - Export Manager Module
Generates seed datasets (JSON/SQL), automatic playlists, and summary reports.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from config import settings
from src.storage.db_manager import DBManager
from src.storage.file_manager import FileManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ExportManager:
    """Exports data in multiple formats and generates analysis reports."""

    def __init__(self, db_manager: Optional[DBManager] = None, export_dir: Optional[Path] = None):
        self.db = db_manager or DBManager()
        self.fm = FileManager()
        self.export_dir = export_dir or settings.EXPORT_DIR
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_all_json(self) -> Dict[str, Path]:
        """
        Export all collections to individual clean JSON files.
        """
        artists = self.db.get_all_artists()
        albums = self.db.get_all_albums()
        tracks = self.db.get_all_tracks()
        genres = self.db.get_all_genres()
        playlists = self.db.get_all_playlists()

        files: Dict[str, Path] = {}
        exports_map = {
            "artists.json": artists,
            "albums.json": albums,
            "tracks.json": tracks,
            "genres.json": genres,
            "playlists.json": playlists,
        }

        for filename, data in exports_map.items():
            path = self.export_dir / filename
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            files[filename] = path
            logger.info(f"Exported {len(data)} items to {path.name}")

        return files

    def export_sql_seed(self, dialect: str = "postgresql") -> Path:
        """
        Generate SQL INSERT statements for relational databases (PostgreSQL/SQL Server).
        """
        tracks = self.db.get_all_tracks()
        artists = self.db.get_all_artists()
        albums = self.db.get_all_albums()
        genres = self.db.get_all_genres()

        sql_path = self.export_dir / "seed_data.sql"
        lines: List[str] = [
            f"-- Music Streaming Seed Data ({dialect})",
            f"-- Generated on: {datetime.utcnow().isoformat()}",
            "\nBEGIN;\n",
        ]

        def escape_str(val: Any) -> str:
            if val is None:
                return "NULL"
            escaped = str(val).replace("'", "''")
            return f"'{escaped}'"

        # ── 1. Genres ──
        for g in genres:
            slug = escape_str(g.get("slug"))
            name = escape_str(g.get("name"))
            desc = escape_str(g.get("description", ""))
            lines.append(f"INSERT INTO genres (slug, name, description) VALUES ({slug}, {name}, {desc}) ON CONFLICT (slug) DO NOTHING;")

        # ── 2. Artists ──
        for a in artists:
            sid = escape_str(a.get("spotify_id"))
            name = escape_str(a.get("name"))
            img = escape_str(a.get("image_url", ""))
            pop = a.get("popularity", 0)
            fol = a.get("followers", 0)
            lines.append(f"INSERT INTO artists (spotify_id, name, image_url, popularity, followers) VALUES ({sid}, {name}, {img}, {pop}, {fol}) ON CONFLICT (spotify_id) DO NOTHING;")

        # ── 3. Albums ──
        for alb in albums:
            sid = escape_str(alb.get("spotify_id"))
            name = escape_str(alb.get("name"))
            art_sid = escape_str(alb.get("artist_spotify_id"))
            img = escape_str(alb.get("image_url", ""))
            r_date = escape_str(alb.get("release_date"))
            tot = alb.get("total_tracks", 1)
            lines.append(
                f"INSERT INTO albums (spotify_id, name, artist_id, image_url, release_date, total_tracks) "
                f"VALUES ({sid}, {name}, (SELECT id FROM artists WHERE spotify_id={art_sid}), {img}, {r_date}, {tot}) "
                f"ON CONFLICT (spotify_id) DO NOTHING;"
            )

        # ── 4. Tracks ──
        for t in tracks:
            sid = escape_str(t.get("spotify_id"))
            name = escape_str(t.get("name"))
            art_sid = escape_str(t.get("artist_spotify_id"))
            alb_sid = escape_str(t.get("album_spotify_id"))
            dur = t.get("duration", 0)
            pop = t.get("popularity", 0)
            surl = escape_str(t.get("spotify_url", ""))
            lpath = escape_str(t.get("local_path", ""))
            stat = escape_str(t.get("download_status", "pending"))
            fsize = t.get("file_size_bytes", 0)

            lines.append(
                f"INSERT INTO tracks (spotify_id, name, artist_id, album_id, duration, popularity, spotify_url, local_path, download_status, file_size_bytes) "
                f"VALUES ({sid}, {name}, (SELECT id FROM artists WHERE spotify_id={art_sid}), (SELECT id FROM albums WHERE spotify_id={alb_sid}), {dur}, {pop}, {surl}, {lpath}, {stat}, {fsize}) "
                f"ON CONFLICT (spotify_id) DO NOTHING;"
            )

        lines.append("\nCOMMIT;\n")

        with open(sql_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Generated SQL seed file: {sql_path.name}")
        return sql_path

    def generate_playlists(self) -> int:
        """
        Create automatic playlists (e.g. 'Top Pop Hits', 'Most Popular 50', 'New Releases') from tracks in DB.
        """
        all_tracks = self.db.get_all_tracks()
        if not all_tracks:
            return 0

        created_count = 0

        # 1. Overall Most Popular 50
        sorted_by_pop = sorted(all_tracks, key=lambda x: x.get("popularity", 0), reverse=True)
        top_50_ids = [t["spotify_id"] for t in sorted_by_pop[:50]]
        self.db.create_playlist(
            name="Top 50 Most Popular",
            description="The most popular songs across all collected playlists.",
            track_ids=top_50_ids,
        )
        created_count += 1

        # 2. Per-Genre Top 20 Playlists
        genres = self.db.get_all_genres()
        for g in genres:
            slug = g["slug"]
            genre_tracks = [t for t in all_tracks if slug in t.get("genres", [])]
            if len(genre_tracks) >= 5:
                sorted_genre = sorted(genre_tracks, key=lambda x: x.get("popularity", 0), reverse=True)
                g_ids = [t["spotify_id"] for t in sorted_genre[:30]]
                self.db.create_playlist(
                    name=f"Best of {g['name']}",
                    description=f"Curated top {g['name']} hits for your listening pleasure.",
                    track_ids=g_ids,
                )
                created_count += 1

        logger.info(f"Generated {created_count} automatic playlists.")
        return created_count

    def generate_report(self) -> str:
        """
        Generate a comprehensive markdown summary report of the collected dataset.
        """
        stats = self.db.get_statistics()
        storage = self.fm.get_storage_stats()

        total = stats.get("total_tracks", 0)
        completed = stats.get("completed_tracks", 0)
        pending = stats.get("pending_tracks", 0)
        failed = stats.get("failed_tracks", 0)
        success_rate = (completed / total * 100) if total > 0 else 0.0

        genre_dist = stats.get("genre_distribution", {})

        report_lines = [
            "# 📊 Music Data Collection Summary Report",
            f"\n*Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            "\n## 1. Overview Statistics",
            f"- **Total Tracks Crawled:** {total:,}",
            f"- **Completed Downloads (MP3):** {completed:,} ({success_rate:.1f}%)",
            f"- **Pending Downloads:** {pending:,}",
            f"- **Failed Downloads:** {failed:,}",
            f"- **Total Artists:** {stats.get('total_artists', 0):,}",
            f"- **Total Albums:** {stats.get('total_albums', 0):,}",
            f"- **Total Audio Storage:** {storage.get('total_audio_size_mb', 0)} MB",
            "\n## 2. Genre Distribution",
            "| Genre Slug | Track Count |",
            "| :--- | :--- |",
        ]

        for genre, count in sorted(genre_dist.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"| `{genre}` | {count:,} |")

        report_lines.append("\n## 3. Storage Breakdown")
        report_lines.append(f"- Audio Directory: `{storage.get('audio_dir')}`")
        report_lines.append(f"- Images Directory: `{storage.get('images_dir')}`")
        report_lines.append(f"- Total MP3 Files on Disk: {storage.get('total_audio_files')}")

        report_text = "\n".join(report_lines)
        report_file = self.export_dir / "COLLECTION_REPORT.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_text)

        logger.info(f"Saved summary report to {report_file.name}")
        return report_text

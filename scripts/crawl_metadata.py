"""
Crawl Metadata Script v3 (Custom Sourcing Studio & Multi-Tier Deduplication)
Fetches metadata from:
- Curated Playlists
- Artist / Discography Sourcing (by name or Spotify URL)
- Album Sourcing (by name or Spotify URL)
- Free Keyword Search (V-Pop, Indie, Acoustic...)
- Custom Spotify URL
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Reconfigure stdout for Windows console UTF-8 support
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

from config import settings
from src.collectors.spotify_collector import SpotifyCollector
from src.processors.deduplicator import Deduplicator
from src.processors.genre_mapper import GenreMapper
from src.storage.db_manager import DBManager
from src.utils.logger import get_logger

console = Console()
logger = get_logger("crawl_metadata")


@click.command()
@click.option("--mode", "-m", default="curated", type=click.Choice(["curated", "playlist", "artist", "album", "search"], case_sensitive=False), help="Crawl mode.")
@click.option("--query", "-q", default=None, help="Query string, Artist name, Album name, or Spotify URL.")
@click.option("--genre", "-g", default=None, help="Override genre category (e.g. 'vpop', 'pop', 'rock', 'rnb', 'ballad').")
@click.option("--limit", "-l", default=50, help="Max tracks to collect per source/query.")
@click.option("--playlists-file", "-p", default="config/playlists.json", help="Path to curated playlists JSON config.")
def main(mode: str, query: Optional[str], genre: Optional[str], limit: int, playlists_file: str):
    console.print("\n[bold cyan]🚀 Starting Spotify Metadata Crawl (Custom Studio v3)...[/bold cyan]\n")

    # 1. Initialize Spotify Collector & DB
    try:
        collector = SpotifyCollector()
    except Exception as e:
        console.print(f"[bold red]❌ Failed to initialize Spotify Collector:[/bold red] {e}")
        sys.exit(1)

    db = DBManager()
    all_raw_tracks: List[Dict[str, Any]] = []

    # 2. Execute crawl based on mode
    if mode == "curated" and not query:
        # Crawl all curated playlists from config/playlists.json
        p_path = Path(playlists_file)
        if not p_path.exists():
            console.print(f"[bold red]Config file {playlists_file} not found![/bold red]")
            sys.exit(1)

        with open(p_path, "r", encoding="utf-8") as f:
            target_playlists = json.load(f).get("playlists", [])

        console.print(f"Processing [bold green]{len(target_playlists)}[/bold green] curated playlists...\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Crawling playlists...", total=len(target_playlists))
            for pl in target_playlists:
                pl_name = pl.get("name", "Unknown")
                pl_url = pl.get("url", "")
                pl_genre = pl.get("genre", "pop")
                target_count = pl.get("target_tracks", limit)

                progress.update(task, description=f"[cyan]Crawling: [bold]{pl_name}[/bold]...")
                try:
                    tracks = collector.collect_playlist_tracks(pl_url, max_tracks=target_count, default_genre=pl_genre)
                    for t in tracks:
                        if pl_genre and pl_genre not in t.get("genres", []):
                            t["genres"].append(pl_genre)
                    all_raw_tracks.extend(tracks)
                    db.upsert_genre(pl_genre, pl_name)
                except Exception as err:
                    logger.error(f"Error crawling playlist {pl_name}: {err}")
                progress.advance(task)

    else:
        # Custom mode (artist, album, search, single playlist/URL)
        target_query = query or ""
        if not target_query:
            console.print("[bold red]Please specify a query with --query / -q for custom crawl mode.[/bold red]")
            sys.exit(1)

        console.print(f"Mode: [bold yellow]{mode.upper()}[/bold yellow] | Query: [bold green]{target_query}[/bold green] | Genre: [bold cyan]{genre or 'auto'}[/bold cyan] | Limit: {limit}\n")
        tracks = collector.collect_custom(mode=mode, query=target_query, max_tracks=limit, default_genre=genre)
        all_raw_tracks.extend(tracks)
        if genre:
            db.upsert_genre(genre, genre.upper())

    console.print(f"\nCollected [bold cyan]{len(all_raw_tracks)}[/bold cyan] total raw track records.")

    # 3. Multi-Tier Deduplication against existing DB
    console.print("Running Multi-Tier Deduplication Engine...")
    existing_db_tracks = db.get_all_tracks()
    unique_new, updated_existing, skipped_dups = Deduplicator.dedup_tracks(
        tracks=all_raw_tracks,
        existing_db_tracks=existing_db_tracks,
    )

    console.print(f"  • [bold green]{len(unique_new)}[/bold green] Brand New Unique Tracks")
    console.print(f"  • [bold yellow]{len(updated_existing)}[/bold yellow] Existing Tracks Updated / Genres Merged")
    console.print(f"  • [bold blue]{len(skipped_dups)}[/bold blue] Redundant Duplicates Filtered")

    # 4. Resolve & Save Entities into Database
    console.print("\nSaving entities into Database...")
    all_active_tracks = unique_new + updated_existing
    artists_map = collector.collect_artists_info([t.get("artist_spotify_id") for t in all_active_tracks], tracks=all_active_tracks)
    albums_map = collector.collect_albums_info([t.get("album_spotify_id") for t in all_active_tracks], tracks=all_active_tracks)

    if artists_map:
        db.bulk_upsert_artists(list(artists_map.values()))
    if albums_map:
        db.bulk_upsert_albums(list(albums_map.values()))
    if unique_new:
        db.bulk_upsert_tracks(unique_new)
    if updated_existing:
        db.bulk_upsert_tracks(updated_existing)

    stats = db.get_statistics()
    console.print("\n[bold green]🎉 Metadata crawl complete![/bold green]")
    console.print(f"  • Total Tracks in DB: [bold]{stats['total_tracks']}[/bold]")
    console.print(f"  • Total Artists: [bold]{stats['total_artists']}[/bold]")
    console.print(f"  • Total Albums: [bold]{stats['total_albums']}[/bold]")
    console.print(f"  • Total Genres: [bold]{len(stats.get('genre_distribution', {}))}[/bold]")
    console.print("\nYou can now proceed to download audio files with: [cyan]python scripts/download_audio.py[/cyan]\n")


if __name__ == "__main__":
    main()

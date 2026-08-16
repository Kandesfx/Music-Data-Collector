"""
Download Audio Script v2
Batch downloads audio tracks with SQLite session checkpoints, crash recovery, and health auto-pause.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

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
from src.downloaders.download_manager import DownloadManager
from src.storage.db_manager import DBManager
from src.utils.session_manager import SessionManager
from src.utils.proxy_manager import ProxyManager

console = Console()


@click.command()
@click.option("--limit", "-l", default=50, help="Maximum number of tracks to download in this run.")
@click.option("--delay", "-d", default=settings.DOWNLOAD_DELAY_SECONDS, help="Delay in seconds between consecutive songs.")
@click.option("--batch-size", "-b", default=settings.BATCH_SIZE, help="Batch size before taking a cooldown pause.")
@click.option("--cooldown", "-c", default=settings.BATCH_COOLDOWN_SECONDS, help="Cooldown in seconds between batches.")
@click.option("--retry-failed", is_flag=True, help="Download previously failed tracks instead of pending.")
@click.option("--proxy/--no-proxy", default=settings.PROXY_ENABLED, help="Enable or disable proxy rotation.")
def main(limit: int, delay: float, batch_size: int, cooldown: int, retry_failed: bool, proxy: bool):
    console.print("\n[bold cyan]🎧 Starting Music Audio Downloader v2...[/bold cyan]\n")

    db = DBManager()
    sm = SessionManager()
    pm = ProxyManager(enabled=proxy)
    dm = DownloadManager(db_manager=db, session_manager=sm, proxy_manager=pm)

    # 1. Fetch target tracks from DB
    target_status = "failed" if retry_failed else "pending"
    tracks = db.get_tracks_by_status(status=target_status, limit=limit)

    if not tracks:
        console.print(f"[bold yellow]No '{target_status}' tracks found in database.[/bold yellow]")
        console.print("If you haven't crawled metadata yet, run: [cyan]python scripts/crawl_metadata.py[/cyan]\n")
        return

    # 2. Filter out already checkpointed completed tracks (crash resume)
    completed_ids = sm.get_completed_spotify_ids()
    if not retry_failed:
        tracks = [t for t in tracks if t.get("spotify_id") not in completed_ids]

    if not tracks:
        console.print("[bold green]All targeted tracks have already been successfully downloaded![/bold green]\n")
        return

    console.print(f"Targeting [bold green]{len(tracks)}[/bold green] tracks to download.")
    console.print(
        f"Config: [dim]Delay: {delay}s | Batch: {batch_size} | Cooldown: {cooldown}s | "
        f"Proxy: {'ON' if pm.enabled else 'OFF'} | Browser Cookies: {settings.COOKIES_FROM_BROWSER or 'None'}[/dim]\n"
    )

    # 3. Batch download with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing...", total=len(tracks))

        def on_progress(info: Dict[str, Any]):
            tr = info["track"]
            h_stat = info["health"]["health"]
            color = "green" if h_stat == "HEALTHY" else "yellow" if h_stat == "DEGRADED" else "red"
            stage = info.get("stage", "finished")
            if stage == "starting":
                progress.update(
                    task,
                    description=f"[cyan]Downloading: [bold]{tr.get('artist_name')} - {tr.get('name')}[/bold] "
                    f"([{color}]{h_stat}[/{color}])",
                )
            elif stage == "finished":
                progress.advance(task)

        results = dm.download_batch(
            tracks=tracks,
            delay_seconds=delay,
            batch_size=batch_size,
            cooldown_seconds=cooldown,
            progress_callback=on_progress,
        )

    console.print("\n[bold green]🏁 Download Run Finished![/bold green]")
    console.print(f"  • Successful: [green]{results.get('successful', 0)}[/green]")
    console.print(f"  • Failed: [red]{results.get('failed', 0)}[/red]")
    console.print("\nNext step: Validate audio integrity with [cyan]python scripts/process_files.py --fix-tags[/cyan]\n")


if __name__ == "__main__":
    main()

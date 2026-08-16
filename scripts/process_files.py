"""
Process Files Script
Scans, validates MP3 integrity, checks durations/bitrates, fixes ID3 tags, and cleans corrupted files.
"""

import sys
from pathlib import Path

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
from src.processors.post_processor import PostProcessor
from src.storage.db_manager import DBManager
from src.storage.file_manager import FileManager

console = Console(force_terminal=True, legacy_windows=False)


@click.command()
@click.option("--fix-tags", is_flag=True, default=True, help="Embed/fix ID3 tags (Title, Artist, Album, Cover Art).")
@click.option("--delete-invalid", is_flag=True, default=False, help="Delete corrupted or unreadable audio files.")
def main(fix_tags: bool, delete_invalid: bool):
    console.print("\n[bold cyan]🔧 Starting Audio File Processing & Validation...[/bold cyan]\n")

    db = DBManager()
    fm = FileManager()
    audio_files = list(settings.AUDIO_DIR.glob("**/*.mp3"))

    if not audio_files:
        console.print("[bold yellow]No MP3 audio files found in audio directory.[/bold yellow]\n")
        return

    console.print(f"Found [bold green]{len(audio_files)}[/bold green] MP3 files to inspect.\n")

    valid_count = 0
    corrupted_count = 0
    fixed_tags_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing files...", total=len(audio_files))

        for file_path in audio_files:
            progress.update(task, description=f"[cyan]Validating: [bold]{file_path.name[:35]}[/bold]...")

            is_valid, err = PostProcessor.validate_audio_file(file_path)

            # Try to match with DB metadata if spotify_id is in filename (e.g. {spotify_id}_{title}.mp3)
            spotify_id = file_path.name.split("_")[0] if "_" in file_path.name else None
            track_meta = db.get_track(spotify_id) if spotify_id else None

            if is_valid:
                valid_count += 1
                if fix_tags and track_meta:
                    if PostProcessor.fix_id3_tags(file_path, track_meta):
                        fixed_tags_count += 1
            else:
                corrupted_count += 1
                console.print(f"[red]⚠️ Corrupted/Invalid:[/red] {file_path.name} -> {err}")
                if delete_invalid:
                    fm.remove_file(file_path)
                    if spotify_id:
                        db.update_track_download_status(spotify_id, status="failed", error=err)
                    console.print(f"  [dim]Deleted corrupted file: {file_path.name}[/dim]")

            progress.advance(task)

    stats = fm.get_storage_stats()

    console.print("\n[bold green]✅ Audio Processing Completed![/bold green]")
    console.print(f"  • Valid MP3 Files: [green]{valid_count:,}[/green]")
    console.print(f"  • Corrupted / Invalid: [red]{corrupted_count:,}[/red]")
    console.print(f"  • ID3 Tags Updated: [cyan]{fixed_tags_count:,}[/cyan]")
    console.print(f"  • Total Audio Storage: [bold]{stats['total_audio_size_mb']} MB[/bold]\n")


if __name__ == "__main__":
    main()

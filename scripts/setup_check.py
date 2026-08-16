"""
Setup & Environment Verification Script v2
Checks if all prerequisites, dependencies, tools, runtimes (Deno, FFmpeg), and credentials are ready.
"""

import sys
import shutil
import subprocess
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Reconfigure stdout for Windows console UTF-8 support
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.table import Table
from config import settings
from src.storage.db_manager import DBManager
from src.utils.session_manager import SessionManager

console = Console(force_terminal=True, legacy_windows=False)


def check_tool(name: str, command: list) -> bool:
    """Check if a CLI tool is installed and responds."""
    try:
        res = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.returncode == 0
    except Exception:
        return False


def main():
    console.print("\n[bold cyan]🔍 Checking Music Data Collector v2 Prerequisites...[/bold cyan]\n")

    table = Table(title="Environment, Runtimes & Tools Checklist", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan", width=22)
    table.add_column("Status", width=14)
    table.add_column("Details", style="dim")

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 9)
    table.add_row("Python Version", "[green]OK[/green]" if py_ok else "[red]FAIL[/red]", f"Version {py_ver} (>= 3.9 required)")

    # 2. Deno Runtime (Critical for YouTube 2026 bypass)
    deno_path = shutil.which("deno")
    deno_ok = deno_path is not None
    table.add_row(
        "Deno Runtime (2026)",
        "[green]FOUND[/green]" if deno_ok else "[yellow]RECOMMENDED[/yellow]",
        deno_path or "Install: winget install DenoLand.Deno",
    )

    # 3. FFmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    ffmpeg_ok = ffmpeg_path is not None
    table.add_row(
        "FFmpeg Audio Decoder",
        "[green]OK[/green]" if ffmpeg_ok else "[yellow]MISSING[/yellow]",
        ffmpeg_path or "Run: spotdl --download-ffmpeg",
    )

    # 4. spotDL
    spotdl_ok = check_tool("spotdl", [sys.executable, "-m", "spotdl", "--help"])
    table.add_row("spotDL", "[green]OK[/green]" if spotdl_ok else "[red]MISSING[/red]", "Python module spotdl")

    # 5. yt-dlp
    ytdlp_ok = check_tool("yt-dlp", [sys.executable, "-m", "yt_dlp", "--version"])
    table.add_row("yt-dlp", "[green]OK[/green]" if ytdlp_ok else "[red]MISSING[/red]", "Python module yt-dlp")

    # 6. Spotify Credentials
    sp_ok = bool(settings.SPOTIFY_CLIENT_ID and settings.SPOTIFY_CLIENT_SECRET)
    table.add_row(
        "Spotify API Keys",
        "[green]CONFIGURED[/green]" if sp_ok else "[red]MISSING[/red]",
        f"Client ID: {'*' * 8 if sp_ok else 'Not set in .env'}",
    )

    # 7. Browser Cookies & Cookie File
    browser_c = settings.COOKIES_FROM_BROWSER
    cookies_file = settings.YOUTUBE_COOKIES_PATH.exists()
    if browser_c:
        cookie_status = f"[green]BROWSER ({browser_c.upper()})[/green]"
        cookie_detail = f"Auto-reading cookies from {browser_c} browser"
    elif cookies_file:
        cookie_status = "[green]FILE FOUND[/green]"
        cookie_detail = str(settings.YOUTUBE_COOKIES_PATH)
    else:
        cookie_status = "[yellow]OPTIONAL[/yellow]"
        cookie_detail = "Set COOKIES_FROM_BROWSER=chrome or export cookies.txt"
    table.add_row("YouTube Cookies", cookie_status, cookie_detail)

    # 8. Proxy Pool
    proxy_status = f"[cyan]ENABLED ({len(settings.PROXY_LIST)})[/cyan]" if settings.PROXY_ENABLED else "[dim]DISABLED[/dim]"
    table.add_row("Proxy Rotation", proxy_status, f"Strategy: {settings.PROXY_ROTATION}")

    # 9. SQLite Session DB
    try:
        sm = SessionManager()
        db_stats = sm.get_session_stats()
        session_ok = True
        session_detail = f"Path: {settings.SESSION_DB_PATH.name} ({db_stats['total_checkpoints']} checkpoints)"
    except Exception as e:
        session_ok = False
        session_detail = str(e)
    table.add_row("Session DB (SQLite)", "[green]READY[/green]" if session_ok else "[red]FAIL[/red]", session_detail)

    # 10. MongoDB Connection
    db = DBManager()
    mongo_ok = db.is_connected()
    table.add_row(
        "MongoDB",
        "[green]CONNECTED[/green]" if mongo_ok else "[yellow]DISCONNECTED[/yellow]",
        f"URI: {settings.MONGO_URI} (DB: {settings.MONGO_DB_NAME})",
    )

    # 11. Dashboard Web UI
    try:
        import flask
        import flask_socketio
        ui_ok = True
        ui_detail = f"Host: http://{settings.DASHBOARD_HOST}:{settings.DASHBOARD_PORT}"
    except ImportError:
        ui_ok = False
        ui_detail = "pip install flask flask-socketio"
    table.add_row("Dashboard UI", "[green]READY[/green]" if ui_ok else "[yellow]MISSING[/yellow]", ui_detail)

    console.print(table)

    console.print("\n[bold]Suggested Actions:[/bold]")
    if not sp_ok:
        console.print("  • Copy [yellow]config/.env.example[/yellow] to [yellow]config/.env[/yellow] and set [cyan]SPOTIFY_CLIENT_ID[/cyan] and [cyan]SPOTIFY_CLIENT_SECRET[/cyan].")
    if not ffmpeg_ok:
        console.print("  • Install FFmpeg by running: [cyan]spotdl --download-ffmpeg[/cyan]")
    if not deno_ok:
        console.print("  • (Recommended) Install Deno for YouTube 2026 bypass: [cyan]winget install DenoLand.Deno[/cyan]")
    
    console.print("\n[bold green]Ready to run:[/bold green]")
    console.print("  • [cyan]python scripts/crawl_metadata.py[/cyan]  (Crawl Spotify playlists)")
    console.print("  • [cyan]python scripts/download_audio.py[/cyan]   (Download pending audio)")
    console.print("  • [cyan]python dashboard/app.py[/cyan]            (Launch real-time Web Dashboard)\n")


if __name__ == "__main__":
    main()

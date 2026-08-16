"""
Export Seed Script
Exports database to JSON/SQL seed files, generates automatic playlists, and creates summary reports.
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

from src.storage.db_manager import DBManager
from src.storage.export_manager import ExportManager

console = Console(force_terminal=True, legacy_windows=False)


@click.command()
@click.option("--format", "-f", "export_format", type=click.Choice(["all", "json", "sql"]), default="all")
@click.option("--generate-playlists", is_flag=True, default=True, help="Auto-generate playlists from collected tracks.")
def main(export_format: str, generate_playlists: bool):
    console.print("\n[bold cyan]📦 Starting Data Export & Reporting...[/bold cyan]\n")

    db = DBManager()
    exporter = ExportManager(db_manager=db)

    # 1. Generate Automatic Playlists
    if generate_playlists:
        count = exporter.generate_playlists()
        console.print(f"[green]✅ Generated {count} automatic curated playlists.[/green]")

    # 2. Export JSON files
    if export_format in ("all", "json"):
        json_files = exporter.export_all_json()
        console.print(f"[green]✅ Exported {len(json_files)} JSON datasets to: [bold]{exporter.export_dir}[/bold][/green]")
        for fname, fpath in json_files.items():
            console.print(f"  • [cyan]{fname}[/cyan]")

    # 3. Export SQL Seed
    if export_format in ("all", "sql"):
        sql_file = exporter.export_sql_seed(dialect="postgresql")
        console.print(f"[green]✅ Generated SQL seed script: [bold]{sql_file.name}[/bold][/green]")

    # 4. Generate Markdown Summary Report
    report_text = exporter.generate_report()
    console.print("[green]✅ Generated Collection Summary Report: [bold]data/exports/COLLECTION_REPORT.md[/bold][/green]\n")


if __name__ == "__main__":
    main()

"""
Music Data Collector - Logger Module
Configures structured logging to both console (with Rich) and file.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

from rich.logging import RichHandler
from rich.console import Console

console = Console()

# ─── Log file path ───────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / f"collector_{datetime.now().strftime('%Y%m%d')}.log"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Create and return a logger with both console (Rich) and file handlers.

    Args:
        name: Logger name (typically __name__ of the calling module).
        level: Logging level (default: INFO).

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # ── Console handler (Rich) ──
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )
    console_handler.setLevel(level)
    console_fmt = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_fmt)

    # ── File handler ──
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # File gets everything
    file_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

"""
Music Data Collector - Data Cleaner Module
Normalizes text, Unicode, dates, and file naming conventions.
"""

import re
import unicodedata
from typing import Dict, Any, Optional
from datetime import datetime


class DataCleaner:
    """Provides data cleaning and sanitization utilities."""

    @staticmethod
    def clean_text(text: Optional[str]) -> str:
        """Strip whitespace and normalize Unicode to NFC."""
        if not text:
            return ""
        # Normalize Unicode
        normalized = unicodedata.normalize("NFC", str(text))
        return normalized.strip()

    @staticmethod
    def clean_song_title(title: str) -> str:
        """
        Clean common noise from song titles like '[Official Music Video]', '(Audio)', etc.
        """
        if not title:
            return ""
        cleaned = DataCleaner.clean_text(title)
        
        # Regex patterns to remove audio/video metadata noise in titles
        noise_patterns = [
            r"\[\s*official\s*(music\s*)?video\s*\]",
            r"\(\s*official\s*(music\s*)?video\s*\)",
            r"\[\s*official\s*audio\s*\]",
            r"\(\s*official\s*audio\s*\)",
            r"\[\s*lyric\s*video\s*\]",
            r"\(\s*lyric\s*video\s*\)",
            r"\[\s*audio\s*\]",
            r"\(\s*audio\s*\)",
            r"\[\s*mv\s*\]",
            r"\(\s*mv\s*\)",
            r"\[\s*hd\s*\]",
            r"\[\s*hq\s*\]",
        ]
        for pattern in noise_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def slugify(text: str, max_length: int = 50) -> str:
        """
        Convert text into a URL-friendly, safe filesystem slug.
        Example: "Shape of You (feat. Someone)" -> "shape-of-you-feat-someone"
        """
        if not text:
            return "unknown"

        # Pre-replace Vietnamese special characters like đ/Đ
        processed = str(text).replace("đ", "d").replace("Đ", "D")

        # Normalize Unicode to NFKD to decompose accents
        normalized = unicodedata.normalize("NFKD", processed)
        # Keep ASCII alphanumeric characters
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        # Lowercase and replace non-alphanumeric with hyphens
        slug = re.sub(r"[^\w\s-]", "", ascii_text.lower())
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")

        if not slug:
            # Fallback if text only contained non-Latin characters (e.g. Japanese/Chinese/Korean)
            slug = re.sub(r"[^\w\s-]", "", processed.lower())
            slug = re.sub(r"[-\s]+", "-", slug).strip("-")

        return slug[:max_length] or "untitled"

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Remove illegal filesystem characters from filename."""
        if not filename:
            return "file"
        # Remove chars illegal on Windows/Linux: < > : " / \ | ? *
        cleaned = re.sub(r'[<>:"/\\|?*]', "", filename)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:100]

    @staticmethod
    def parse_release_date(date_str: Optional[str]) -> Optional[str]:
        """
        Parse and standardize release date to ISO format YYYY-MM-DD.
        Spotify provides dates as YYYY, YYYY-MM, or YYYY-MM-DD.
        """
        if not date_str:
            return None

        clean_date = date_str.strip()
        try:
            if len(clean_date) == 4:  # YYYY
                return f"{clean_date}-01-01"
            elif len(clean_date) == 7:  # YYYY-MM
                return f"{clean_date}-01"
            elif len(clean_date) == 10:  # YYYY-MM-DD
                datetime.strptime(clean_date, "%Y-%m-%d")
                return clean_date
        except Exception:
            pass

        return None

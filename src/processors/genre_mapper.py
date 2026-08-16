"""
Music Data Collector - Genre Mapper Module
Maps Spotify's highly detailed/specific genres to standardized application genres.
"""

from typing import List, Dict

GENRE_MAP: Dict[str, str] = {
    # Pop & V-Pop
    "pop": "pop",
    "dance pop": "pop",
    "electropop": "pop",
    "synthpop": "pop",
    "indie pop": "pop",
    "teen pop": "pop",
    "v-pop": "vpop",
    "vietnamese pop": "vpop",
    "vietnamese indie": "vpop",
    "nhac tre": "vpop",
    "vietnamese": "vpop",

    # Rock & Metal
    "rock": "rock",
    "alt rock": "rock",
    "alternative rock": "rock",
    "indie rock": "rock",
    "classic rock": "rock",
    "hard rock": "rock",
    "soft rock": "rock",
    "punk": "rock",
    "metal": "metal",
    "heavy metal": "metal",
    "nu metal": "metal",
    "death metal": "metal",

    # Hip Hop & Rap
    "hip hop": "hiphop",
    "rap": "hiphop",
    "trap": "hiphop",
    "vietnamese hip hop": "hiphop",
    "vietnamese rap": "hiphop",
    "gangster rap": "hiphop",
    "melodic rap": "hiphop",

    # Electronic & Dance
    "electronic": "electronic",
    "edm": "electronic",
    "house": "electronic",
    "techno": "electronic",
    "trance": "electronic",
    "electro": "electronic",
    "dance": "electronic",
    "dubstep": "electronic",
    "drum and bass": "electronic",

    # R&B & Soul
    "r&b": "rnb",
    "rnb": "rnb",
    "soul": "rnb",
    "contemporary r&b": "rnb",
    "urban contemporary": "rnb",

    # Jazz & Blues
    "jazz": "jazz",
    "smooth jazz": "jazz",
    "vocal jazz": "jazz",
    "blues": "blues",
    "acoustic blues": "blues",

    # Classical & Instrumental
    "classical": "classical",
    "piano": "classical",
    "orchestral": "classical",
    "instrumental": "classical",
    "soundtrack": "classical",

    # K-Pop
    "k-pop": "kpop",
    "kpop": "kpop",
    "k-pop boy group": "kpop",
    "k-pop girl group": "kpop",
    "korean r&b": "kpop",

    # Country & Folk
    "country": "country",
    "contemporary country": "country",
    "country road": "country",
    "folk": "folk",
    "acoustic": "folk",
    "singer-songwriter": "folk",

    # Latin & Reggae
    "latin": "latin",
    "reggaeton": "latin",
    "latin pop": "latin",
    "reggae": "reggae",
    "dub": "reggae",

    # Ambient & Chill
    "ambient": "ambient",
    "chill": "ambient",
    "chillout": "ambient",
    "lounge": "ambient",
    "lo-fi": "ambient",
    "lo-fi beats": "ambient",
}


class GenreMapper:
    """Class to standardize genres from Spotify metadata tags."""

    @staticmethod
    def map_genre(genre_text: str) -> str:
        """Map a single genre string to normalized slug."""
        if not genre_text:
            return "other"

        clean = genre_text.lower().strip()

        # Direct match
        if clean in GENRE_MAP:
            return GENRE_MAP[clean]

        # Partial substring match
        for key, value in GENRE_MAP.items():
            if key in clean:
                return value

        return "other"

    @classmethod
    def map_genres(cls, genres_list: List[str]) -> List[str]:
        """Map a list of raw genres to a unique set of normalized slugs."""
        if not genres_list:
            return ["other"]

        mapped = []
        for g in genres_list:
            norm = cls.map_genre(g)
            if norm not in mapped:
                mapped.append(norm)

        # If only 'other' is mapped along with valid ones, remove 'other'
        if len(mapped) > 1 and "other" in mapped:
            mapped.remove("other")

        return mapped or ["other"]

    @classmethod
    def get_primary_genre(cls, genres_list: List[str]) -> str:
        """Get the primary (first non-other) genre from the list."""
        mapped = cls.map_genres(genres_list)
        for g in mapped:
            if g != "other":
                return g
        return mapped[0] if mapped else "other"

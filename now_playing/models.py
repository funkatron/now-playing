"""Domain models."""

from dataclasses import dataclass
from typing import Optional

from now_playing.logging_config import DEFAULT_IDLE_TEXT


@dataclass
class TrackInfo:
    source: str
    state: str
    title: str = ""
    artist: str = ""
    album: str = ""
    year: Optional[int] = None
    artwork_path: str = ""
    updated_at: str = ""

    def to_text(self, idle_text: str = DEFAULT_IDLE_TEXT) -> str:
        if self.state != "playing" or not self.title:
            return idle_text

        year = str(self.year) if self.year else ""
        return f"\"{self.title}\"\n{self.artist}\n{self.album}\n{year}".rstrip()

    def fingerprint(self) -> dict:
        return {
            "source": self.source,
            "state": self.state,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "year": self.year,
            "artwork_path": self.artwork_path,
        }


@dataclass
class ProviderSnapshot:
    source: str
    state: str
    detail: str = ""
    error: Optional[str] = None
    updated_at: str = ""

    def to_payload(self) -> dict:
        return {
            "source": self.source,
            "state": self.state,
            "detail": self.detail,
            "error": self.error,
            "updated_at": self.updated_at,
        }


class ProviderError(RuntimeError):
    pass


"""Spotify provider via AppleScript."""

import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from now_playing.logging_config import LOGGER
from now_playing.models import TrackInfo
from now_playing.util import iso_now, safe_filename


def spotify_artwork_cache_path(title: str, artist: str, album: str, artwork_url: str) -> Path:
    cache_dir = Path.home() / ".now-playing" / "artwork-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    parsed = urllib.parse.urlparse(artwork_url)
    _root, ext = os.path.splitext(parsed.path)
    if not ext:
        ext = ".jpg"
    cache_name = safe_filename(f"spotify_{artist}_{album}_{title}")
    return cache_dir / f"{cache_name}{ext}"


def fetch_spotify_artwork(title: str, artist: str, album: str, artwork_url: str) -> str:
    if not artwork_url:
        return ""

    cache_path = spotify_artwork_cache_path(title, artist, album, artwork_url)
    if cache_path.exists():
        return str(cache_path)

    try:
        req = urllib.request.Request(artwork_url, headers={"User-Agent": "now-playing/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response, cache_path.open("wb") as output:
            output.write(response.read())
    except Exception as exc:  # pragma: no cover - best effort
        LOGGER.debug("Spotify artwork download failed: %s", exc)
        return ""

    return str(cache_path)


def run_osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def spotify_query_script() -> str:
    return """
tell application "Spotify"
    if it is not running then return "not_running"
    set outputParts to {}
    set end of outputParts to (player state as text)
    if player state is playing then
        set end of outputParts to (name of current track as text)
        set end of outputParts to (artist of current track as text)
        set end of outputParts to (album of current track as text)
        set end of outputParts to (artwork url of current track as text)
    end if
    set AppleScript's text item delimiters to (character id 31)
    return outputParts as text
end tell
"""


def query_spotify_snapshot() -> list[str]:
    output = run_osascript(spotify_query_script())
    return output.split(chr(31)) if output else []


def spotify_state(snapshot: list[str]) -> str:
    if not snapshot:
        return "not_running"
    return snapshot[0].strip().lower()


def spotify_track_fields(snapshot: list[str]) -> tuple[str, str, str, str]:
    if len(snapshot) < 5:
        return "", "", "", ""
    return tuple(part.strip() for part in snapshot[1:5])


def get_spotify_track() -> TrackInfo:
    try:
        snapshot = query_spotify_snapshot()
    except subprocess.CalledProcessError as exc:
        LOGGER.debug("Spotify AppleScript query failed: %s", exc)
        return TrackInfo(source="spotify", state="not_running", updated_at=iso_now())

    player_state = spotify_state(snapshot)
    LOGGER.debug("Spotify AppleScript player state: %r", player_state)
    if player_state != "playing":
        state = "not_running" if player_state == "not_running" else "idle"
        return TrackInfo(source="spotify", state=state, updated_at=iso_now())

    title, artist, album, artwork_url = spotify_track_fields(snapshot)
    if not title:
        return TrackInfo(source="spotify", state="idle", updated_at=iso_now())

    return TrackInfo(
        source="spotify",
        state="playing",
        title=title,
        artist=artist,
        album=album,
        artwork_path=fetch_spotify_artwork(title, artist, album, artwork_url),
        updated_at=iso_now(),
    )

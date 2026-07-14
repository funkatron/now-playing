"""Apple Music provider."""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from now_playing.logging_config import LOGGER, PLAYING_STATE_CODE
from now_playing.models import TrackInfo
from now_playing.util import iso_now, safe_filename

_music_app = None
_last_artwork_key: Optional[tuple] = None
_last_artwork_path: str = ""


def reset_apple_music_runtime_state() -> None:
    """Clear cached ScriptingBridge app and artwork shortcut (tests / restart)."""
    global _music_app, _last_artwork_key, _last_artwork_path
    _music_app = None
    _last_artwork_key = None
    _last_artwork_path = ""


@contextmanager
def _autorelease_pool() -> Iterator[None]:
    try:
        import objc

        with objc.autorelease_pool():
            yield
        return
    except Exception:
        pass

    pool = None
    try:
        from Foundation import NSAutoreleasePool

        pool = NSAutoreleasePool.alloc().init()
    except Exception:
        pool = None
    try:
        yield
    finally:
        if pool is not None:
            pool.drain()


def _apple_music_app():
    global _music_app
    import ScriptingBridge

    if _music_app is None:
        _music_app = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Music")
        return _music_app

    try:
        # Touching a dead bridge can raise; recreate on failure.
        _music_app.isRunning()
    except Exception:
        _music_app = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Music")
    return _music_app


def _artwork_cache_key(track) -> tuple:
    return (
        track.databaseID(),
        str(track.artist() or ""),
        str(track.album() or ""),
        str(track.name() or ""),
    )


def _artwork_cache_path(track) -> Path:
    cache_dir = Path.home() / ".now-playing" / "artwork-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    database_id, artist, album, name = _artwork_cache_key(track)
    cache_name = safe_filename(f"{database_id}_{artist}_{album}_{name}")
    return cache_dir / f"{cache_name}.png"


def extract_apple_music_artwork(track) -> str:
    """Return cached PNG path when possible; only decode via AppKit on a miss."""
    global _last_artwork_key, _last_artwork_path

    key = _artwork_cache_key(track)
    if (
        key == _last_artwork_key
        and _last_artwork_path
        and Path(_last_artwork_path).exists()
    ):
        return _last_artwork_path

    cache_path = _artwork_cache_path(track)
    if cache_path.exists():
        _last_artwork_key = key
        _last_artwork_path = str(cache_path)
        return _last_artwork_path

    with _autorelease_pool():
        from AppKit import NSBitmapImageRep, NSPNGFileType

        # Hot path: do not call artworks() until we know there is a cache miss.
        artworks = track.artworks()
        if not artworks:
            return ""

        first_artwork = artworks[0]
        artwork_data = first_artwork.data()
        if not artwork_data:
            return ""

        if hasattr(artwork_data, "TIFFRepresentation"):
            raw_data = artwork_data.TIFFRepresentation()
        elif hasattr(artwork_data, "NSRepresentation"):
            raw_data = artwork_data.NSRepresentation()
        else:
            raw_data = artwork_data

        bitmap_rep = NSBitmapImageRep.imageRepWithData_(raw_data)
        if bitmap_rep is None:
            LOGGER.debug("Apple Music artwork data could not be converted to NSBitmapImageRep.")
            return ""

        png_data = bitmap_rep.representationUsingType_properties_(NSPNGFileType, None)
        if png_data is None:
            LOGGER.debug("Apple Music artwork data could not be converted to PNG.")
            return ""

        png_data.writeToFile_atomically_(str(cache_path), True)

    _last_artwork_key = key
    _last_artwork_path = str(cache_path)
    return _last_artwork_path


def get_apple_music_track() -> TrackInfo:
    with _autorelease_pool():
        music_app = _apple_music_app()
        if not music_app or not music_app.isRunning():
            return TrackInfo(source="apple_music", state="not_running", updated_at=iso_now())

        if music_app.playerState() != PLAYING_STATE_CODE:
            return TrackInfo(source="apple_music", state="idle", updated_at=iso_now())

        current_track = music_app.currentTrack()
        if current_track is None or not current_track.name():
            return TrackInfo(source="apple_music", state="idle", updated_at=iso_now())

        year = current_track.year()
        return TrackInfo(
            source="apple_music",
            state="playing",
            title=str(current_track.name() or ""),
            artist=str(current_track.artist() or ""),
            album=str(current_track.album() or ""),
            year=int(year) if year else None,
            artwork_path=extract_apple_music_artwork(current_track),
            updated_at=iso_now(),
        )

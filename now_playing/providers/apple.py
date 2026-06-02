"""Apple Music provider."""

import subprocess
from pathlib import Path

from now_playing.logging_config import LOGGER, PLAYING_STATE_CODE
from now_playing.models import TrackInfo
from now_playing.util import iso_now, safe_filename


def extract_apple_music_artwork(track) -> str:
    from AppKit import NSBitmapImageRep, NSPNGFileType

    artworks = track.artworks()
    if not artworks:
        return ""

    cache_dir = Path.home() / ".now-playing" / "artwork-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_name = safe_filename(
        f"{track.databaseID()}_{track.artist()}_{track.album()}_{track.name()}"
    )
    cache_path = cache_dir / f"{cache_name}.png"

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
    return str(cache_path)



def get_apple_music_track() -> TrackInfo:
    import ScriptingBridge

    music_app = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Music")
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

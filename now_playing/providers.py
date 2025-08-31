import logging
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import List, Optional


def safe_filename(filename: str) -> str:
    return re.sub(r"[^\w-]", "", filename)


@dataclass
class TrackInfo:
    title: str
    artist: str
    album: str
    year: Optional[str] = None

    def to_four_line_string(self) -> str:
        return f'"{self.title}"\n{self.artist}\n{self.album}\n{self.year or ""}'


class ArtworkCache:
    def __init__(self, cache_dir: Optional[str] = None) -> None:
        self.cache_dir = cache_dir or os.path.expanduser("~/.now-playing/artwork-cache/")
        os.makedirs(self.cache_dir, exist_ok=True)

    def path_for_png(self, key: str) -> str:
        return os.path.join(self.cache_dir, safe_filename(key) + ".png")

    def path_for_ext(self, key: str, default_ext: str) -> str:
        return os.path.join(self.cache_dir, safe_filename(key) + default_ext)

    def download(self, url: str, dest_path: str, timeout: int = 10) -> bool:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "now-playing/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest_path, "wb") as out:
                out.write(resp.read())
            return True
        except Exception as e:  # pragma: no cover - best effort
            logging.debug(f"Artwork download failed: {e}")
            return False


class Provider:
    name: str

    def get_current_track(self) -> Optional[object]:  # provider-specific object
        raise NotImplementedError

    def get_current_song(self) -> str:
        info = self._get_track_info()
        return info.to_four_line_string() if info else "Enjoy the silence."

    def get_artworks(self) -> List[str]:
        raise NotImplementedError

    def _get_track_info(self) -> Optional[TrackInfo]:
        raise NotImplementedError


class AppleMusicProvider(Provider):
    name = "applemusic"

    def __init__(self, artwork_cache: Optional[ArtworkCache] = None) -> None:
        self.cache = artwork_cache or ArtworkCache()

    def _music_app(self):
        import ScriptingBridge

        return ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Music")

    def _is_playing(self) -> bool:
        app = self._music_app()
        return bool(app.isRunning() and app.playerState() == 1800426320)

    def get_current_track(self):
        app = self._music_app()
        logging.debug(f"Music App: {getattr(app, 'properties', lambda: {})()}")
        logging.debug(f"Music App Player State: {getattr(app, 'playerState', lambda: None)()}")
        if self._is_playing():
            try:
                return app.currentTrack()
            except Exception as e:
                logging.debug(f"Error getting currentTrack: {e}")
        return None

    def _get_track_info(self) -> Optional[TrackInfo]:
        track = self.get_current_track()
        if track and track.name():
            return TrackInfo(
                title=track.name(),
                artist=track.artist(),
                album=track.album(),
                year=str(track.year()) if getattr(track, "year", None) else None,
            )
        return None

    def get_artworks(self) -> List[str]:
        track = self.get_current_track()
        if not track:
            return []

        # Apple provides artwork objects with image data; write PNGs
        try:
            from AppKit import NSBitmapImageRep, NSPNGFileType  # type: ignore
        except Exception:
            return []

        artwork_paths: List[str] = []
        for artwork in track.artworks():
            if not artwork.data():
                continue
            bitmap_rep = NSBitmapImageRep.imageRepWithData_(artwork.data().TIFFRepresentation())
            png_data = bitmap_rep.representationUsingType_properties_(NSPNGFileType, None)
            cache_key = f"{track.databaseID()}_{track.artist()}_{track.album()}_{track.name()}"
            dest = self.cache.path_for_png(cache_key)
            # writeToFile mutates the string so pass a copy
            import copy as _copy

            png_data.writeToFile_atomically_(_copy.copy(dest), True)
            artwork_paths.append(dest)
        return artwork_paths


class SpotifyProvider(Provider):
    name = "spotify"

    def __init__(self, artwork_cache: Optional[ArtworkCache] = None) -> None:
        self.cache = artwork_cache or ArtworkCache()

    def _app(self):
        from ScriptingBridge import SBApplication

        return SBApplication.applicationWithBundleIdentifier_("com.spotify.client")

    def _is_playing(self) -> bool:
        app = self._app()
        try:
            state = app.playerState()
            logging.debug(f"Spotify playerState: {state}")
        except Exception:
            state = None
        return bool(app.isRunning() and state == 1800426320)

    def get_current_track(self):
        app = self._app()
        logging.debug(f"Spotify isRunning: {app.isRunning()}")
        if self._is_playing():
            try:
                return app.currentTrack()
            except Exception as e:
                logging.debug(f"Error getting currentTrack: {e}")
        return None

    def _get_track_info(self) -> Optional[TrackInfo]:
        track = self.get_current_track()
        if track and track.name():
            return TrackInfo(
                title=track.name(),
                artist=track.artist(),
                album=track.album(),
                year=None,
            )
        return None

    def get_artworks(self) -> List[str]:
        track = self.get_current_track()
        if not track:
            return []

        try:
            artwork_url = track.artworkUrl()
        except Exception:
            artwork_url = None

        if not artwork_url:
            return []

        parsed = urllib.parse.urlparse(artwork_url)
        _, ext = os.path.splitext(parsed.path)
        if not ext:
            ext = ".jpg"

        cache_key = f"{getattr(track, 'id', lambda: '')()}_{track.artist()}_{track.album()}_{track.name()}"
        dest = self.cache.path_for_ext(cache_key, ext)
        if not os.path.exists(dest):
            self.cache.download(artwork_url, dest)
        return [dest] if os.path.exists(dest) else []



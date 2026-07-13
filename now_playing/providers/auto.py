"""Provider selection and diagnostics."""

import time
from typing import Optional

from now_playing.logging_config import LOGGER
from now_playing.models import ProviderError, ProviderSnapshot, TrackInfo
from now_playing.providers.apple import get_apple_music_track
from now_playing.providers.spotify import get_spotify_track
from now_playing.util import iso_now

_SPOTIFY_DIAGNOSTICS_TTL_SECONDS = 60.0
_spotify_diagnostics_cache: Optional[dict] = None
_spotify_diagnostics_cached_at: float = 0.0
_last_apple_playing_key: Optional[tuple[str, str, str]] = None


def reset_spotify_diagnostics_cache() -> None:
    global _spotify_diagnostics_cache, _spotify_diagnostics_cached_at, _last_apple_playing_key
    _spotify_diagnostics_cache = None
    _spotify_diagnostics_cached_at = 0.0
    _last_apple_playing_key = None


def _apple_playing_key(track: TrackInfo) -> tuple[str, str, str]:
    return (track.title, track.artist, track.album)


def _should_refresh_spotify_diagnostics(apple_track: TrackInfo) -> bool:
    global _last_apple_playing_key
    key = _apple_playing_key(apple_track)
    if key != _last_apple_playing_key:
        _last_apple_playing_key = key
        return True
    return (time.time() - _spotify_diagnostics_cached_at) >= _SPOTIFY_DIAGNOSTICS_TTL_SECONDS


def _cache_spotify_snapshot(snapshot: ProviderSnapshot) -> dict:
    global _spotify_diagnostics_cache, _spotify_diagnostics_cached_at
    payload = snapshot.to_payload()
    _spotify_diagnostics_cache = payload
    _spotify_diagnostics_cached_at = time.time()
    return payload


def _cached_spotify_diagnostics_payload() -> dict:
    if _spotify_diagnostics_cache is not None:
        return _spotify_diagnostics_cache
    return provider_snapshot(
        TrackInfo(source="spotify", state="not_running", updated_at=iso_now())
    ).to_payload()


def provider_snapshot(track: TrackInfo, detail: str = "", error: Optional[str] = None) -> ProviderSnapshot:
    return ProviderSnapshot(
        source=track.source,
        state=track.state,
        detail=detail,
        error=error,
        updated_at=track.updated_at,
    )


def inspect_provider(source: str) -> tuple[TrackInfo, ProviderSnapshot]:
    try:
        if source == "apple_music":
            track = get_apple_music_track()
            detail = "Apple Music automation"
        elif source == "spotify":
            track = get_spotify_track()
            detail = "Spotify AppleScript"
        else:
            raise ProviderError(f"Unsupported source: {source}")
    except Exception as exc:
        LOGGER.exception("Provider %s failed", source)
        track = TrackInfo(source=source, state="error", updated_at=iso_now())
        return track, provider_snapshot(track, error=str(exc))

    if track.state == "playing":
        now_playing = " / ".join(part for part in [track.title, track.artist, track.album] if part)
        detail = now_playing or detail
    snapshot = provider_snapshot(track, detail=detail)
    LOGGER.debug(
        "Provider %s state=%s detail=%s error=%s",
        source,
        snapshot.state,
        snapshot.detail,
        snapshot.error,
    )
    return track, snapshot


def select_track_with_diagnostics(source: str) -> tuple[TrackInfo, dict]:
    if source == "apple_music":
        track, snapshot = inspect_provider("apple_music")
        return track, {"apple_music": snapshot.to_payload()}
    if source == "spotify":
        track, snapshot = inspect_provider("spotify")
        return track, {"spotify": snapshot.to_payload()}
    if source != "auto":
        raise ProviderError(f"Unsupported source: {source}")

    apple_track, apple_snapshot = inspect_provider("apple_music")
    if apple_track.state == "playing":
        if _should_refresh_spotify_diagnostics(apple_track):
            _, spotify_snapshot = inspect_provider("spotify")
            spotify_payload = _cache_spotify_snapshot(spotify_snapshot)
        else:
            spotify_payload = _cached_spotify_diagnostics_payload()
        return apple_track, {
            "apple_music": apple_snapshot.to_payload(),
            "spotify": spotify_payload,
        }

    spotify_track, spotify_snapshot = inspect_provider("spotify")
    if spotify_track.state == "playing":
        return spotify_track, {
            "apple_music": apple_snapshot.to_payload(),
            "spotify": spotify_snapshot.to_payload(),
        }

    if apple_track.state != "not_running":
        return apple_track, {
            "apple_music": apple_snapshot.to_payload(),
            "spotify": spotify_snapshot.to_payload(),
        }

    return spotify_track, {
        "apple_music": apple_snapshot.to_payload(),
        "spotify": spotify_snapshot.to_payload(),
    }


def select_track(source: str) -> TrackInfo:
    return select_track_with_diagnostics(source)[0]

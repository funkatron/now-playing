"""Provider selection and diagnostics."""

from typing import Optional

from now_playing.logging_config import LOGGER
from now_playing.models import ProviderError, ProviderSnapshot, TrackInfo
from now_playing.providers.apple import get_apple_music_track
from now_playing.providers.spotify import get_spotify_track
from now_playing.util import iso_now


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
        return apple_track, {
            "apple_music": apple_snapshot.to_payload(),
            "spotify": inspect_provider("spotify")[1].to_payload(),
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

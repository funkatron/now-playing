"""Track source providers (np service + legacy __main__ path)."""

from now_playing.providers.apple import extract_apple_music_artwork, get_apple_music_track
from now_playing.providers.auto import (
    inspect_provider,
    provider_snapshot,
    select_track,
    select_track_with_diagnostics,
)
from now_playing.providers.legacy import (
    AppleMusicProvider,
    ArtworkCache,
    Provider,
    SpotifyProvider,
    TrackInfo as LegacyTrackInfo,
)
from now_playing.providers.spotify import (
    fetch_spotify_artwork,
    get_spotify_track,
    query_spotify_snapshot,
    run_osascript,
    spotify_artwork_cache_path,
    spotify_query_script,
    spotify_state,
    spotify_track_fields,
)

__all__ = [
    "AppleMusicProvider",
    "ArtworkCache",
    "LegacyTrackInfo",
    "Provider",
    "SpotifyProvider",
    "extract_apple_music_artwork",
    "fetch_spotify_artwork",
    "get_apple_music_track",
    "get_spotify_track",
    "inspect_provider",
    "provider_snapshot",
    "query_spotify_snapshot",
    "run_osascript",
    "select_track",
    "select_track_with_diagnostics",
    "spotify_artwork_cache_path",
    "spotify_query_script",
    "spotify_state",
    "spotify_track_fields",
]

import pytest

from now_playing.__main__ import resolve_provider
from now_playing.providers import AppleMusicProvider, SpotifyProvider


def test_resolve_provider_apple_aliases(tmp_path):
    for alias in ("applemusic", "apple", "music"):
        provider, song_file, artworks_file, obs_source = resolve_provider(alias)
        assert isinstance(provider, AppleMusicProvider)
        assert song_file.endswith("apple_current_song.txt")
        assert artworks_file.endswith("apple_now_playing_artworks.txt")
        assert obs_source == "NPImageApple"


def test_resolve_provider_spotify_aliases(tmp_path):
    for alias in ("spotify", "sp"):
        provider, song_file, artworks_file, obs_source = resolve_provider(alias)
        assert isinstance(provider, SpotifyProvider)
        assert song_file.endswith("spotify_current_song.txt")
        assert artworks_file.endswith("spotify_now_playing_artworks.txt")
        assert obs_source == "NPImageSpotify"


def test_resolve_provider_unknown_raises():
    with pytest.raises(SystemExit):
        resolve_provider("unknown-source")



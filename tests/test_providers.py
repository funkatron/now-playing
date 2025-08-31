import types

from now_playing.providers import SpotifyProvider, AppleMusicProvider, ArtworkCache


class DummyTrack:
    def __init__(self, name="N", artist="A", album="Al", year=None, id_="id", artwork_url=None):
        self._name = name
        self._artist = artist
        self._album = album
        self._year = year
        self._id = id_
        self._artwork_url = artwork_url

    def name(self):
        return self._name

    def artist(self):
        return self._artist

    def album(self):
        return self._album

    def year(self):
        return self._year

    def id(self):
        return self._id

    def artworkUrl(self):
        return self._artwork_url


class DummyApp:
    def __init__(self, is_running=True, state=1800426320, track=None):
        self._is_running = is_running
        self._state = state
        self._track = track

    def isRunning(self):
        return self._is_running

    def playerState(self):
        return self._state

    def currentTrack(self):
        return self._track


def test_spotify_provider_info_and_artwork(monkeypatch, tmp_path):
    track = DummyTrack(name="Song", artist="Artist", album="Album", artwork_url="https://example.com/c.png")
    app = DummyApp(track=track)

    def fake_app():
        return app

    # Avoid network by faking download and cache path
    provider = SpotifyProvider(artwork_cache=ArtworkCache(cache_dir=str(tmp_path)))
    monkeypatch.setattr(provider, "_app", fake_app)
    monkeypatch.setattr(provider.cache, "download", lambda url, dest: (tmp_path / "c.png").write_text("x") is None)

    info = provider.get_current_song()
    assert info.splitlines()[:3] == ['"Song"', 'Artist', 'Album']

    images = provider.get_artworks()
    assert len(images) == 1


def test_apple_provider_info_monkeypatch(monkeypatch):
    track = DummyTrack(name="S", artist="Ar", album="Al", year=2024)
    app = DummyApp(track=track)

    def fake_music_app():
        return app

    provider = AppleMusicProvider()
    monkeypatch.setattr(provider, "_music_app", fake_music_app)

    info = provider.get_current_song()
    assert info.splitlines() == ['"S"', 'Ar', 'Al', '2024']



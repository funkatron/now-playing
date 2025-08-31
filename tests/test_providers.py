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
    def fake_download(url, dest):
        import pathlib
        pathlib.Path(dest).write_text("x")
        return True
    monkeypatch.setattr(provider.cache, "download", fake_download)

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


def test_apple_provider_artwork_writes_png(monkeypatch, tmp_path):
    # Fake AppKit module that writes a file when writeToFile_atomically_ is called
    import types, sys, pathlib

    class FakePNGData:
        def __init__(self, dests):
            self.dests = dests
        def writeToFile_atomically_(self, dest, flag):
            # simulate writing to path
            pathlib.Path(dest).write_text("png")

    class FakeBitmap:
        def __init__(self, dests):
            self.dests = dests
        @classmethod
        def imageRepWithData_(cls, _):
            return cls([])
        def representationUsingType_properties_(self, _type, _props):
            return FakePNGData(self.dests)
        def pixelsWide(self):
            return 100
        def pixelsHigh(self):
            return 100
        def bitsPerPixel(self):
            return 32

    fake_appkit = types.ModuleType("AppKit")
    fake_appkit.NSBitmapImageRep = FakeBitmap
    fake_appkit.NSPNGFileType = object()
    monkeypatch.setitem(sys.modules, "AppKit", fake_appkit)

    # Dummy track with artworks providing data with TIFFRepresentation()
    class Data:
        def TIFFRepresentation(self):
            return b"tiff"
    class Art:
        def data(self):
            return Data()
    class Track:
        def __init__(self):
            self._id = 1
        def artworks(self):
            return [Art()]
        def databaseID(self):
            return 1
        def artist(self):
            return "A"
        def album(self):
            return "Al"
        def name(self):
            return "N"

    prov = AppleMusicProvider(artwork_cache=ArtworkCache(cache_dir=str(tmp_path)))
    monkeypatch.setattr(prov, "get_current_track", lambda: Track())

    imgs = prov.get_artworks()
    assert len(imgs) == 1
    assert imgs[0].endswith(".png")
    assert (tmp_path / (imgs[0].split("/")[-1])).exists()


def test_spotify_provider_default_ext_and_download(monkeypatch, tmp_path):
    # artwork url without extension should default to .jpg
    track = DummyTrack(name="S", artist="A", album="Al", artwork_url="https://example.com/cover")
    app = DummyApp(track=track)

    def fake_app():
        return app

    prov = SpotifyProvider(artwork_cache=ArtworkCache(cache_dir=str(tmp_path)))
    monkeypatch.setattr(prov, "_app", fake_app)

    def fake_download(url, dest):
        import pathlib
        pathlib.Path(dest).write_text("jpg")
        return True
    monkeypatch.setattr(prov.cache, "download", fake_download)

    imgs = prov.get_artworks()
    assert len(imgs) == 1
    assert imgs[0].endswith(".jpg")
    assert (tmp_path / (imgs[0].split("/")[-1])).exists()



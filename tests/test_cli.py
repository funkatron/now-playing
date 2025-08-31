import sys
from types import SimpleNamespace


class FakeProvider:
    def __init__(self, info: str, images: list[str]):
        self._info = info
        self._images = images

    def get_current_song(self) -> str:
        return self._info

    def get_artworks(self) -> list[str]:
        return list(self._images)


def test_cli_info_writes_and_prints(monkeypatch, tmp_path, capsys):
    # Arrange
    song_file = tmp_path / "apple_current_song.txt"
    artworks_file = tmp_path / "apple_now_playing_artworks.txt"
    provider = FakeProvider('"Track"\nArtist\nAlbum\n2024', [str(tmp_path / "art.png")])

    import now_playing.__main__ as cli

    def fake_resolve(_source: str):
        return provider, str(song_file), str(artworks_file), "NPImageApple"

    monkeypatch.setattr(cli, "resolve_provider", fake_resolve)
    monkeypatch.setenv("PYTHON_LOG_LEVEL", "WARNING")

    # Act
    monkeypatch.setattr(sys, "argv", ["now_playing", "applemusic", "--info"]) 
    cli.main()

    # Assert
    out = capsys.readouterr().out.strip()
    assert out == '"Track"\nArtist\nAlbum\n2024'
    assert song_file.read_text() == '"Track"\nArtist\nAlbum\n2024'
    # Artworks file should be written as part of --info run
    assert artworks_file.exists()


def test_cli_image_writes_list_and_prints_first(monkeypatch, tmp_path, capsys):
    img1 = tmp_path / "cover1.png"
    img1.write_text("dummy")
    song_file = tmp_path / "apple_current_song.txt"
    artworks_file = tmp_path / "apple_now_playing_artworks.txt"
    provider = FakeProvider('"Track"\nArtist\nAlbum\n2024', [str(img1)])

    import now_playing.__main__ as cli

    def fake_resolve(_source: str):
        return provider, str(song_file), str(artworks_file), "NPImageApple"

    monkeypatch.setattr(cli, "resolve_provider", fake_resolve)
    monkeypatch.setenv("PYTHON_LOG_LEVEL", "WARNING")

    monkeypatch.setattr(sys, "argv", ["now_playing", "applemusic", "--image"]) 
    cli.main()

    out = capsys.readouterr().out.strip()
    assert out == str(img1)
    # Artworks list file contains the image path and trailing newline
    assert artworks_file.read_text() == f"{img1}\n"


def test_cli_update_obs_calls_client(monkeypatch, tmp_path):
    img1 = tmp_path / "cover.png"
    img1.write_text("dummy")
    song_file = tmp_path / "spotify_current_song.txt"
    artworks_file = tmp_path / "spotify_now_playing_artworks.txt"
    provider = FakeProvider('"T"\nA\nAl\n', [str(img1)])

    import now_playing.__main__ as cli

    def fake_resolve(_source: str):
        return provider, str(song_file), str(artworks_file), "NPImageSpotify"

    class FakeOBS:
        def __init__(self, *args, **kwargs):
            self.calls = []
        def update_image_source(self, source_name: str, file_path: str) -> None:
            self.calls.append((source_name, file_path))

    fake_obs_instance = FakeOBS()

    def fake_obs_ctor(*args, **kwargs):
        return fake_obs_instance

    monkeypatch.setattr(cli, "resolve_provider", fake_resolve)
    monkeypatch.setattr(cli, "OBSClient", fake_obs_ctor)
    monkeypatch.setenv("PYTHON_LOG_LEVEL", "WARNING")

    monkeypatch.setattr(sys, "argv", ["now_playing", "spotify", "--update-obs"]) 
    cli.main()

    # OBS client called with correct source and path
    assert fake_obs_instance.calls == [("NPImageSpotify", str(img1))]
    # Artworks list written
    assert artworks_file.read_text() == f"{img1}\n"



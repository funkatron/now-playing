import json
import threading
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace

import np_service
import pytest


def test_main_defaults_to_current_json(monkeypatch, capsys):
    track = np_service.TrackInfo(
        source="spotify",
        state="not_running",
        updated_at="2026-03-17T15:16:49-04:00",
    )

    monkeypatch.setattr(np_service, "load_config_env", lambda: None)
    monkeypatch.setattr(np_service, "configure_logging", lambda: None)
    monkeypatch.setattr(np_service, "logs_dir", lambda: None)
    monkeypatch.setattr(
        np_service,
        "select_track_with_diagnostics",
        lambda source: (track, {"spotify": {"source": "spotify", "state": "not_running"}}),
    )

    exit_code = np_service.main([])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] == "spotify"
    assert payload["state"] == "not_running"
    assert payload["providers"]["spotify"]["state"] == "not_running"


def test_load_config_env_sets_defaults_without_overwriting(monkeypatch, tmp_path):
    config_path = tmp_path / "config.env"
    config_path.write_text(
        "NOW_PLAYING_SOURCE=spotify\n"
        "NOW_PLAYING_IDLE_TEXT=Idle text\n"
        "PYTHON_LOG_LEVEL=DEBUG\n"
    )

    monkeypatch.setattr(np_service, "config_env_file", lambda: config_path)
    monkeypatch.delenv("NOW_PLAYING_IDLE_TEXT", raising=False)
    monkeypatch.setenv("NOW_PLAYING_SOURCE", "apple_music")
    monkeypatch.delenv("PYTHON_LOG_LEVEL", raising=False)

    np_service.load_config_env()

    assert np_service.os.environ["NOW_PLAYING_SOURCE"] == "apple_music"
    assert np_service.os.environ["NOW_PLAYING_IDLE_TEXT"] == "Idle text"
    assert np_service.os.environ["PYTHON_LOG_LEVEL"] == "DEBUG"


def test_materialize_outputs_uses_stable_artwork_path(monkeypatch, tmp_path):
    repo_root = tmp_path
    data_root = repo_root / "_data"
    data_root.mkdir()

    source_artwork = tmp_path / "source.png"
    source_artwork.write_bytes(b"artwork")

    monkeypatch.setattr(np_service, "repo_dir", lambda: repo_root)

    track = np_service.TrackInfo(
        source="apple_music",
        state="playing",
        title="Track",
        artist="Artist",
        album="Album",
        year=2024,
        artwork_path=str(source_artwork),
        updated_at="2026-03-17T16:00:00-04:00",
    )

    first = np_service.materialize_outputs(track, "")
    second = np_service.materialize_outputs(track, "")

    stable_artwork_path = str(data_root / "current_artwork.png")

    assert first["payload"]["artwork_path"] == stable_artwork_path
    assert first["text_changed"] is True
    assert second["text_changed"] is False


def test_extract_apple_music_artwork_accepts_nsrepresentation(monkeypatch, tmp_path):
    written_paths = []

    class FakePNGData:
        def writeToFile_atomically_(self, dest, _flag):
            Path(dest).write_bytes(b"png")
            written_paths.append(dest)

    class FakeBitmap:
        @classmethod
        def imageRepWithData_(cls, data):
            assert data == b"descriptor-bytes"
            return cls()

        def representationUsingType_properties_(self, _file_type, _props):
            return FakePNGData()

    class FakeArtworkData:
        def NSRepresentation(self):
            return b"descriptor-bytes"

    class FakeArtwork:
        def data(self):
            return FakeArtworkData()

    class FakeTrack:
        def artworks(self):
            return [FakeArtwork()]

        def databaseID(self):
            return 42

        def artist(self):
            return "Artist"

        def album(self):
            return "Album"

        def name(self):
            return "Song"

    monkeypatch.setattr(np_service.Path, "home", lambda: tmp_path)
    monkeypatch.setitem(
        np_service.sys.modules,
        "AppKit",
        SimpleNamespace(NSBitmapImageRep=FakeBitmap, NSPNGFileType=object()),
    )

    result = np_service.extract_apple_music_artwork(FakeTrack())

    assert result.endswith("42_Artist_Album_Song.png")
    assert Path(result).exists()
    assert written_paths == [result]


def test_track_info_text_and_fingerprint():
    track = np_service.TrackInfo(
        source="apple_music",
        state="playing",
        title="Track",
        artist="Artist",
        album="Album",
        year=2024,
        artwork_path="/tmp/cover.png",
        updated_at="2026-03-17T16:00:00-04:00",
    )

    assert track.to_text("") == '"Track"\nArtist\nAlbum\n2024'
    assert track.fingerprint() == {
        "source": "apple_music",
        "state": "playing",
        "title": "Track",
        "artist": "Artist",
        "album": "Album",
        "year": 2024,
        "artwork_path": "/tmp/cover.png",
    }


def test_is_playing_state_accepts_scriptingbridge_and_string_values():
    assert np_service.is_playing_state(np_service.PLAYING_STATE_CODE) is True
    assert np_service.is_playing_state("playing") is True
    assert np_service.is_playing_state(" Playing ") is True
    assert np_service.is_playing_state("paused") is False
    assert np_service.is_playing_state(None) is False


def test_spotify_snapshot_helpers():
    snapshot = ["playing", "Song", "Artist", "Album", "https://example.com/cover.jpg"]

    assert "tell application \"Spotify\"" in np_service.spotify_query_script()
    assert np_service.spotify_state(snapshot) == "playing"
    assert np_service.spotify_state([]) == "not_running"
    assert np_service.spotify_track_fields(snapshot) == (
        "Song",
        "Artist",
        "Album",
        "https://example.com/cover.jpg",
    )
    assert np_service.spotify_track_fields(["playing"]) == ("", "", "", "")


def test_file_helpers_round_trip(tmp_path):
    text_path = tmp_path / "value.txt"
    json_path = tmp_path / "value.json"
    copy_src = tmp_path / "src.txt"
    copy_dest = tmp_path / "dest.txt"

    assert np_service.write_text_if_changed(text_path, "hello") is True
    assert np_service.write_text_if_changed(text_path, "hello") is False

    assert np_service.write_json_if_changed(json_path, {"b": 1, "a": 2}) is True
    assert np_service.write_json_if_changed(json_path, {"a": 2, "b": 1}) is False

    copy_src.write_text("copy-me")
    assert np_service.copy_file_if_changed(copy_src, copy_dest) is True
    assert np_service.copy_file_if_changed(copy_src, copy_dest) is False
    assert np_service.remove_file_if_exists(copy_dest) is True
    assert np_service.remove_file_if_exists(copy_dest) is False


def test_read_previous_state_invalid_json(monkeypatch, tmp_path):
    state_path = tmp_path / "sync_state.json"
    state_path.write_text("{bad json")
    monkeypatch.setattr(np_service, "state_file", lambda: state_path)
    assert np_service.read_previous_state() == {}


def test_read_current_payload_prefers_existing_json(monkeypatch, tmp_path):
    current_path = tmp_path / "current_track.json"
    payload = {"source": "spotify", "state": "idle", "text": ""}
    current_path.write_text(json.dumps(payload))
    monkeypatch.setattr(np_service, "current_track_json_file", lambda: current_path)
    assert np_service.read_current_payload("") == {**payload, "artwork_path": None}


def test_read_current_payload_falls_back_to_sync(monkeypatch, tmp_path):
    current_path = tmp_path / "current_track.json"
    current_path.write_text("{bad json")
    monkeypatch.setattr(np_service, "current_track_json_file", lambda: current_path)
    monkeypatch.setattr(np_service, "sync", lambda source, idle_text, namespace="current": {"track": {"source": "apple_music", "state": "idle"}})
    assert np_service.read_current_payload("") == {"source": "apple_music", "state": "idle"}


def test_select_track_auto_prefers_playing_sources(monkeypatch):
    idle_apple = np_service.TrackInfo(source="apple_music", state="idle", updated_at="now")
    playing_apple = np_service.TrackInfo(source="apple_music", state="playing", updated_at="now")
    playing_spotify = np_service.TrackInfo(source="spotify", state="playing", updated_at="now")
    not_running_spotify = np_service.TrackInfo(source="spotify", state="not_running", updated_at="now")

    monkeypatch.setattr(np_service, "get_apple_music_track", lambda: playing_apple)
    monkeypatch.setattr(np_service, "get_spotify_track", lambda: playing_spotify)
    assert np_service.select_track("auto").source == "apple_music"

    monkeypatch.setattr(np_service, "get_apple_music_track", lambda: idle_apple)
    monkeypatch.setattr(np_service, "get_spotify_track", lambda: playing_spotify)
    assert np_service.select_track("auto").source == "spotify"

    monkeypatch.setattr(np_service, "get_apple_music_track", lambda: idle_apple)
    monkeypatch.setattr(np_service, "get_spotify_track", lambda: not_running_spotify)
    assert np_service.select_track("auto").source == "apple_music"

    with pytest.raises(np_service.ProviderError):
        np_service.select_track("bad-source")


def test_select_track_with_diagnostics_reports_both_sources(monkeypatch):
    apple = np_service.TrackInfo(source="apple_music", state="idle", updated_at="now")
    spotify = np_service.TrackInfo(source="spotify", state="playing", title="Song", updated_at="now")

    monkeypatch.setattr(
        np_service,
        "inspect_provider",
        lambda source: (
            apple if source == "apple_music" else spotify,
            np_service.ProviderSnapshot(source=source, state=("idle" if source == "apple_music" else "playing"), updated_at="now"),
        ),
    )

    track, providers = np_service.select_track_with_diagnostics("auto")

    assert track.source == "spotify"
    assert providers["apple_music"]["state"] == "idle"
    assert providers["spotify"]["state"] == "playing"


def test_get_spotify_track_uses_applescript_output(monkeypatch):
    monkeypatch.setattr(
        np_service,
        "query_spotify_snapshot",
        lambda: ["playing", "Song", "Artist", "Album", "https://example.com/cover.jpg"],
    )
    monkeypatch.setattr(np_service, "fetch_spotify_artwork", lambda *args: "/tmp/cover.jpg")
    monkeypatch.setattr(np_service, "iso_now", lambda: "2026-03-19T17:45:00-04:00")

    track = np_service.get_spotify_track()

    assert track.source == "spotify"
    assert track.state == "playing"
    assert track.title == "Song"
    assert track.artist == "Artist"
    assert track.album == "Album"
    assert track.artwork_path == "/tmp/cover.jpg"


def test_update_obs_disabled(monkeypatch):
    monkeypatch.delenv("OBSWS_ENABLED", raising=False)
    track = np_service.TrackInfo(source="spotify", state="idle", updated_at="now")
    assert np_service.update_obs(track, "") is False


def test_update_obs_enabled(monkeypatch, tmp_path):
    artwork_path = tmp_path / "current_artwork.png"
    artwork_path.write_bytes(b"img")
    monkeypatch.setenv("OBSWS_ENABLED", "1")
    monkeypatch.setenv("OBSWS_PASSWORD", "secret")
    monkeypatch.setenv("OBSWS_TEXT_INPUT_NAME", "NPText")
    monkeypatch.setattr(np_service, "current_artwork_file", lambda: artwork_path)

    calls = []

    class FakeRequests:
        @staticmethod
        def SetInputSettings(**kwargs):
            return kwargs

    class FakeWS:
        def __init__(self, host, port, password):
            calls.append(("ctor", host, port, password))

        def connect(self):
            calls.append(("connect",))

        def call(self, request):
            calls.append(("call", request))

        def disconnect(self):
            calls.append(("disconnect",))

    monkeypatch.setitem(
        np_service.sys.modules,
        "obswebsocket",
        SimpleNamespace(obsws=FakeWS, requests=FakeRequests),
    )

    track = np_service.TrackInfo(
        source="apple_music",
        state="playing",
        artwork_path=str(artwork_path),
        updated_at="now",
    )

    assert np_service.update_obs(track, "hello") is True
    assert ("ctor", "localhost", 4455, "secret") in calls
    assert any(call[0] == "call" and call[1]["inputName"] == "NPImage" for call in calls)
    assert any(call[0] == "call" and call[1]["inputName"] == "NPText" for call in calls)


def test_sync_updates_obs_only_when_track_changes(monkeypatch, tmp_path):
    repo_root = tmp_path
    data_root = repo_root / "_data"
    data_root.mkdir()
    source_artwork = repo_root / "cover.png"
    source_artwork.write_bytes(b"artwork")

    monkeypatch.setattr(np_service, "repo_dir", lambda: repo_root)
    monkeypatch.setattr(np_service, "read_previous_state", lambda namespace="current": {})

    def make_track():
        return np_service.TrackInfo(
            source="apple_music",
            state="playing",
            title="Track",
            artist="Artist",
            album="Album",
            artwork_path=str(source_artwork),
            updated_at="now",
        )

    monkeypatch.setattr(
        np_service,
        "select_track_with_diagnostics",
        lambda source: (
            make_track(),
            {
                "apple_music": {
                    "source": "apple_music",
                    "state": "playing",
                    "detail": "Track / Artist / Album",
                    "error": None,
                    "updated_at": "now",
                }
            },
        ),
    )

    obs_calls = []
    monkeypatch.setattr(np_service, "update_obs", lambda track, text: obs_calls.append((track.source, text)) or True)

    first = np_service.sync("auto", "")
    assert first["changed"] is True
    assert first["track"]["providers"]["apple_music"]["state"] == "playing"
    assert obs_calls == [("apple_music", '"Track"\nArtist\nAlbum')]

    monkeypatch.setattr(np_service, "read_previous_state", lambda namespace="current": {
        "track": {
            "source": "apple_music",
            "state": "playing",
            "title": "Track",
            "artist": "Artist",
            "album": "Album",
            "year": None,
            "artwork_path": str(data_root / "current_artwork.png"),
        },
        "updated_at": "older-timestamp",
    })
    np_service.write_json_if_changed(
        data_root / "current_track.json",
        {
            "source": "apple_music",
            "state": "playing",
            "title": "Track",
            "artist": "Artist",
            "album": "Album",
            "year": None,
            "artwork_path": str(data_root / "current_artwork.png"),
            "updated_at": "older-timestamp",
            "text": '"Track"\nArtist\nAlbum',
            "providers": {
                "apple_music": {
                    "source": "apple_music",
                    "state": "playing",
                    "detail": "Track / Artist / Album",
                    "error": None,
                    "updated_at": "now",
                }
            },
        },
    )
    second = np_service.sync("auto", "")
    assert second["changed"] is False
    assert second["json_changed"] is False
    assert second["track"]["updated_at"] == "older-timestamp"
    assert obs_calls == [("apple_music", '"Track"\nArtist\nAlbum')]


def test_request_handler_endpoints():
    payload = {
        "source": "spotify",
        "state": "idle",
        "text": "",
        "artwork_path": None,
        "providers": {
            "apple_music": {"source": "apple_music", "state": "idle", "detail": "", "error": None, "updated_at": "now"},
            "spotify": {"source": "spotify", "state": "idle", "detail": "", "error": None, "updated_at": "now"},
        },
    }
    server = np_service.NowPlayingHTTPServer(("127.0.0.1", 0), np_service.RequestHandler, lambda: payload)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("GET", "/health")
        health = json.loads(conn.getresponse().read().decode("utf-8"))
        assert health == {"status": "ok"}

        conn.request("GET", "/")
        dashboard = conn.getresponse().read().decode("utf-8")
        assert "Now Playing" in dashboard
        assert "EventSource" in dashboard
        assert "connectEvents()" in dashboard
        assert "/current_artwork.png" in dashboard
        assert "Apple Music" in dashboard

        conn.request("GET", "/overlay")
        overlay = conn.getresponse().read().decode("utf-8")
        assert "background: transparent;" in overlay
        assert "justify-content: center;" in overlay
        assert 'const endpointPrefix = "";' in overlay
        assert "overlay overlay-compact" in overlay
        assert "-webkit-line-clamp: 2;" in overlay
        assert "Funkatron" not in overlay
        assert "Live local feed for stream overlays" not in overlay

        conn.request("GET", "/overlay?preset=tv")
        overlay_tv = conn.getresponse().read().decode("utf-8")
        assert "overlay overlay-tv" in overlay_tv
        assert "clamp(64px, 8vw, 124px)" in overlay_tv
        assert ".overlay.overlay-tv.has-art::before" in overlay_tv
        assert "transform: scale(1.12);" in overlay_tv
        assert 'overlayEl.style.setProperty("--artwork-url"' in overlay_tv

        conn.request("GET", "/overlay?hide_status=1&max_lines=1&panel_opacity=0.45")
        overlay_tuned = conn.getresponse().read().decode("utf-8")
        assert "overlay-hide-status" in overlay_tuned
        assert "-webkit-line-clamp: 1;" in overlay_tuned
        assert "rgba(10, 12, 15, 0.45)" in overlay_tuned

        conn.request("GET", "/current")
        current = json.loads(conn.getresponse().read().decode("utf-8"))
        assert current["source"] == "spotify"

        conn.request("GET", "/current.txt")
        assert conn.getresponse().read().decode("utf-8") == ""

        conn.request("GET", "/artwork")
        artwork = json.loads(conn.getresponse().read().decode("utf-8"))
        assert artwork == {"artwork_path": None}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_request_handler_artwork_file(monkeypatch, tmp_path):
    artwork_path = tmp_path / "current_artwork.png"
    artwork_path.write_bytes(b"png-bytes")
    monkeypatch.setattr(np_service, "current_artwork_file", lambda: artwork_path)

    server = np_service.NowPlayingHTTPServer(("127.0.0.1", 0), np_service.RequestHandler, lambda: {})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("GET", "/current_artwork.png")
        response = conn.getresponse()
        assert response.status == 200
        assert response.getheader("Content-Type") == "image/png"
        assert response.read() == b"png-bytes"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_request_handler_spotify_namespaced_endpoints(monkeypatch, tmp_path):
    spotify_json = tmp_path / "spotify_current_track.json"
    spotify_json.write_text(
        json.dumps(
            {
                "source": "spotify",
                "state": "playing",
                "title": "Song",
                "artist": "Artist",
                "album": "Album",
                "artwork_path": str(tmp_path / "spotify_current_artwork.png"),
                "text": '"Song"\nArtist\nAlbum',
                "providers": {
                    "spotify": {
                        "source": "spotify",
                        "state": "playing",
                        "detail": "Song / Artist / Album",
                        "error": None,
                        "updated_at": "now",
                    }
                },
                "updated_at": "now",
                "year": None,
            }
        )
    )
    spotify_artwork = tmp_path / "spotify_current_artwork.png"
    spotify_artwork.write_bytes(b"png-bytes")

    monkeypatch.setattr(np_service, "namespaced_current_track_json_file", lambda namespace="current": spotify_json if namespace == "spotify" else tmp_path / "unused.json")
    monkeypatch.setattr(np_service, "namespaced_current_artwork_file", lambda namespace="current": spotify_artwork if namespace == "spotify" else tmp_path / "unused.png")

    server = np_service.NowPlayingHTTPServer(("127.0.0.1", 0), np_service.RequestHandler, lambda: {})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("GET", "/spotify/current")
        current = json.loads(conn.getresponse().read().decode("utf-8"))
        assert current["source"] == "spotify"
        assert current["state"] == "playing"

        conn.request("GET", "/spotify/current.txt")
        assert conn.getresponse().read().decode("utf-8") == '"Song"\nArtist\nAlbum'

        conn.request("GET", "/spotify/artwork")
        artwork = json.loads(conn.getresponse().read().decode("utf-8"))
        assert artwork["artwork_path"] == str(spotify_artwork)

        conn.request("GET", "/spotify/current_artwork.png")
        response = conn.getresponse()
        assert response.status == 200
        assert response.read() == b"png-bytes"

        conn.request("GET", "/spotify/overlay")
        spotify_overlay = conn.getresponse().read().decode("utf-8")
        assert "background: transparent;" in spotify_overlay
        assert 'const endpointPrefix = "/spotify";' in spotify_overlay
        assert "overlay overlay-compact" in spotify_overlay
        assert "connectEvents()" in spotify_overlay

        conn.request("GET", "/spotify/overlay?preset=tv")
        spotify_overlay_tv = conn.getresponse().read().decode("utf-8")
        assert "overlay overlay-tv" in spotify_overlay_tv
        assert 'const endpointPrefix = "/spotify";' in spotify_overlay_tv
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_overlay_uses_env_defaults(monkeypatch):
    server = np_service.NowPlayingHTTPServer(("127.0.0.1", 0), np_service.RequestHandler, lambda: {})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("NOW_PLAYING_OVERLAY_PRESET", "tv")
        monkeypatch.setenv("NOW_PLAYING_OVERLAY_HIDE_STATUS", "1")
        monkeypatch.setenv("NOW_PLAYING_OVERLAY_MAX_LINES", "1")
        monkeypatch.setenv("NOW_PLAYING_OVERLAY_PANEL_OPACITY", "0.50")

        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("GET", "/overlay")
        overlay = conn.getresponse().read().decode("utf-8")
        assert "overlay overlay-tv" in overlay
        assert "overlay-hide-status" in overlay
        assert "-webkit-line-clamp: 1;" in overlay
        assert "rgba(10, 12, 15, 0.50)" in overlay
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_template_path_overrides(monkeypatch, tmp_path):
    dashboard_template = tmp_path / "dashboard.html"
    overlay_template = tmp_path / "overlay.html"
    dashboard_template.write_text("<html><body>DASH __ENDPOINT_PREFIX__ __USE_SSE__</body></html>")
    overlay_template.write_text(
        "<html><body>OVER __ENDPOINT_PREFIX__ __USE_SSE__ __OVERLAY_PRESET__ "
        "__OVERLAY_STATUS_CLASS__ __OVERLAY_MAX_LINES__ __OVERLAY_PANEL_OPACITY__</body></html>"
    )

    monkeypatch.setenv("NOW_PLAYING_DASHBOARD_TEMPLATE_PATH", str(dashboard_template))
    monkeypatch.setenv("NOW_PLAYING_OVERLAY_TEMPLATE_PATH", str(overlay_template))

    server = np_service.NowPlayingHTTPServer(("127.0.0.1", 0), np_service.RequestHandler, lambda: {})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("GET", "/")
        dashboard = conn.getresponse().read().decode("utf-8")
        assert "DASH" in dashboard
        assert "true" in dashboard

        conn.request("GET", "/overlay?preset=tv&panel_opacity=0.55")
        overlay = conn.getresponse().read().decode("utf-8")
        assert "OVER" in overlay
        assert "tv" in overlay
        assert "0.55" in overlay
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_invalid_template_override_warns_and_falls_back(monkeypatch, tmp_path, caplog):
    bad_overlay = tmp_path / "bad-overlay.html"
    bad_overlay.write_text("<html><body>bad template without required tokens</body></html>")
    monkeypatch.setenv("NOW_PLAYING_OVERLAY_TEMPLATE_PATH", str(bad_overlay))
    caplog.set_level("WARNING", logger="now_playing")

    server = np_service.NowPlayingHTTPServer(("127.0.0.1", 0), np_service.RequestHandler, lambda: {})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("GET", "/overlay")
        overlay = conn.getresponse().read().decode("utf-8")
        assert "Now Playing Overlay" in overlay
        assert "overlay overlay-compact" in overlay
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "Ignoring NOW_PLAYING_OVERLAY_TEMPLATE_PATH template" in caplog.text
    assert "missing placeholders" in caplog.text


def test_install_and_uninstall_service(monkeypatch, tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs_root = repo_root / "_logs"
    data_root = repo_root / "_data"
    launch_agents = tmp_path / "LaunchAgents"
    plist_path = launch_agents / "custom.label.plist"

    monkeypatch.setattr(np_service, "repo_dir", lambda: repo_root)
    monkeypatch.setattr(np_service, "logs_dir", lambda: logs_root.mkdir(exist_ok=True) or logs_root)
    monkeypatch.setattr(np_service, "data_dir", lambda: data_root.mkdir(exist_ok=True) or data_root)
    monkeypatch.setattr(np_service, "launch_agent_path", lambda: plist_path)
    monkeypatch.setattr(np_service, "launch_agent_label", lambda: "custom.label")
    monkeypatch.setattr(np_service.os, "getuid", lambda: 501)
    monkeypatch.setenv("NOW_PLAYING_HOST", "127.0.0.1")
    monkeypatch.setenv("NOW_PLAYING_PORT", "8976")

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(np_service.subprocess, "run", fake_run)

    assert np_service.install_service() == 0
    assert plist_path.exists()
    plist_text = plist_path.read_bytes()
    assert b"np_service.py" in plist_text
    assert any(command[:2] == ["launchctl", "bootstrap"] for command in calls)

    assert np_service.uninstall_service() == 0
    assert not plist_path.exists()
    assert any(command[:2] == ["launchctl", "bootout"] for command in calls)

    output = capsys.readouterr().out
    assert "Installed custom.label" in output
    assert "Removed custom.label" in output


def test_install_service_tolerates_transient_bootstrap_failure(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs_root = repo_root / "_logs"
    data_root = repo_root / "_data"
    launch_agents = tmp_path / "LaunchAgents"
    plist_path = launch_agents / "custom.label.plist"

    monkeypatch.setattr(np_service, "repo_dir", lambda: repo_root)
    monkeypatch.setattr(np_service, "logs_dir", lambda: logs_root.mkdir(exist_ok=True) or logs_root)
    monkeypatch.setattr(np_service, "data_dir", lambda: data_root.mkdir(exist_ok=True) or data_root)
    monkeypatch.setattr(np_service, "launch_agent_path", lambda: plist_path)
    monkeypatch.setattr(np_service, "launch_agent_label", lambda: "custom.label")
    monkeypatch.setattr(np_service.os, "getuid", lambda: 501)
    monkeypatch.setattr(np_service.time, "sleep", lambda _: None)

    calls = []

    def fake_run(command, check=False, **kwargs):
        calls.append(command)
        if command[:2] == ["launchctl", "bootstrap"]:
            raise np_service.subprocess.CalledProcessError(5, command)
        if command[:2] == ["launchctl", "print"]:
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(np_service.subprocess, "run", fake_run)

    assert np_service.install_service() == 0
    assert plist_path.exists()
    assert any(command[:2] == ["launchctl", "print"] for command in calls)


def test_service_status_reports_install_and_runtime_state(monkeypatch, tmp_path, capsys):
    plist_path = tmp_path / "com.funkatron.now-playing.plist"
    plist_path.write_text("plist")
    log_path = tmp_path / "launchd.log"

    monkeypatch.setattr(np_service, "launch_agent_path", lambda: plist_path)
    monkeypatch.setattr(np_service, "launch_agent_label", lambda: "com.funkatron.now-playing")
    monkeypatch.setattr(np_service, "logs_dir", lambda: tmp_path)
    monkeypatch.setattr(np_service, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(np_service, "service_is_loaded", lambda _label_ref: True)
    monkeypatch.setattr(np_service, "service_pid", lambda _label_ref: 12345)
    monkeypatch.setenv("NOW_PLAYING_HOST", "127.0.0.1")
    monkeypatch.setenv("NOW_PLAYING_PORT", "8976")
    monkeypatch.setenv("OBSWS_ENABLED", "1")
    monkeypatch.setenv("OBSWS_HOST", "localhost")
    monkeypatch.setenv("OBSWS_PORT", "4455")
    monkeypatch.setenv("OBSWS_PASSWORD", "secret")
    monkeypatch.setenv("OBSWS_IMAGE_INPUT_NAME", "NPImage")
    monkeypatch.setenv("OBSWS_TEXT_INPUT_NAME", "NPText")
    monkeypatch.setenv("OBSWS_TEXT_FIELD", "text")

    assert np_service.service_status() == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["installed"] is True
    assert payload["loaded"] is True
    assert payload["running"] is True
    assert payload["pid"] == 12345
    assert payload["url"] == "http://127.0.0.1:8976/"
    assert payload["obs"]["browser_overlay_url"] == "http://127.0.0.1:8976/overlay"
    assert payload["obs"]["spotify_overlay_url"] == "http://127.0.0.1:8976/spotify/overlay"
    assert payload["obs"]["files"]["song"] == str(tmp_path / "current_song.txt")
    assert payload["obs"]["files"]["artwork"] == str(tmp_path / "current_artwork.png")
    assert payload["obs"]["websocket"]["enabled"] is True
    assert payload["obs"]["websocket"]["host"] == "localhost"
    assert payload["obs"]["websocket"]["port"] == 4455
    assert payload["obs"]["websocket"]["image_input_name"] == "NPImage"
    assert payload["obs"]["websocket"]["text_input_name"] == "NPText"


def test_spotify_session_command_and_terminal_detection(monkeypatch, tmp_path):
    monkeypatch.setattr(np_service, "repo_dir", lambda: tmp_path)
    assert "spotify-session-serve" in np_service.spotify_session_command(5)
    assert np_service.detect_terminal_app("terminal") == "terminal"
    monkeypatch.setattr(np_service.Path, "exists", lambda self: str(self) == "/Applications/iTerm.app")
    assert np_service.detect_terminal_app("auto") == "iterm"


def test_start_and_stop_spotify_session(monkeypatch, tmp_path, capsys):
    pid_path = tmp_path / "spotify-session.pid"
    monkeypatch.setattr(np_service, "spotify_session_pid_file", lambda: pid_path)
    monkeypatch.setattr(np_service, "detect_terminal_app", lambda preference: "terminal")
    monkeypatch.setattr(np_service, "launch_terminal_session", lambda command, terminal: None)
    monkeypatch.setattr(np_service, "service_http_url", lambda: "http://127.0.0.1:8976/")

    assert np_service.start_spotify_session(5, "auto") == 0
    assert "Launched Spotify session in terminal" in capsys.readouterr().out

    pid_path.write_text("12345")
    killed = []
    monkeypatch.setattr(np_service.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    assert np_service.stop_spotify_session() == 0
    assert killed == [(12345, 15)]
    assert not pid_path.exists()


def test_run_spotify_session_writes_spotify_namespace(monkeypatch, tmp_path):
    pid_path = tmp_path / "spotify-session.pid"
    monkeypatch.setattr(np_service, "spotify_session_pid_file", lambda: pid_path)
    calls = []

    def fake_sync(source, idle_text, namespace):
        calls.append((source, idle_text, namespace))
        raise KeyboardInterrupt

    monkeypatch.setattr(np_service, "sync", fake_sync)

    assert np_service.run_spotify_session(5, "") == 0
    assert calls == [("spotify", "", "spotify")]


def test_tail_service_log_prints_recent_lines(monkeypatch, tmp_path, capsys):
    log_path = tmp_path / "launchd.log"
    log_path.write_text("one\ntwo\nthree\n")
    monkeypatch.setattr(np_service, "logs_dir", lambda: tmp_path)

    assert np_service.tail_service_log(lines=2, follow=False) == 0
    assert capsys.readouterr().out == "two\nthree\n"


def test_start_stop_and_restart_service(monkeypatch, tmp_path, capsys):
    plist_path = tmp_path / "com.funkatron.now-playing.plist"
    plist_path.write_text("plist")

    monkeypatch.setattr(np_service, "launch_agent_path", lambda: plist_path)
    monkeypatch.setattr(np_service, "launch_agent_label", lambda: "com.funkatron.now-playing")
    monkeypatch.setattr(np_service, "launchctl_domain", lambda: "gui/501")
    monkeypatch.setattr(np_service, "launchctl_label_ref", lambda: "gui/501/com.funkatron.now-playing")
    monkeypatch.setattr(np_service, "service_http_url", lambda: "http://127.0.0.1:8976/")

    calls = []
    loaded_state = {"loaded": False}

    def fake_service_is_loaded(_label_ref):
        return loaded_state["loaded"]

    def fake_run(command, check=False, **kwargs):
        calls.append(command)
        if command[:2] == ["launchctl", "bootstrap"]:
            loaded_state["loaded"] = True
        if command[:2] == ["launchctl", "bootout"]:
            loaded_state["loaded"] = False
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(np_service, "service_is_loaded", fake_service_is_loaded)
    monkeypatch.setattr(np_service.subprocess, "run", fake_run)

    assert np_service.start_service() == 0
    assert np_service.restart_service() == 0
    assert np_service.stop_service() == 0

    output = capsys.readouterr().out
    assert "Started com.funkatron.now-playing" in output
    assert "Stopped com.funkatron.now-playing" in output
    assert any(command[:2] == ["launchctl", "bootstrap"] for command in calls)
    assert any(command[:2] == ["launchctl", "kickstart"] for command in calls)
    assert any(command[:2] == ["launchctl", "bootout"] for command in calls)

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
    monkeypatch.setattr(np_service, "select_track", lambda source: track)

    exit_code = np_service.main([])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] == "spotify"
    assert payload["state"] == "not_running"


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
    assert json.loads((data_root / "current_track.json").read_text())["artwork_path"] == stable_artwork_path
    assert first["json_changed"] is True
    assert second["json_changed"] is False


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
    assert np_service.read_current_payload("") == payload


def test_read_current_payload_falls_back_to_sync(monkeypatch, tmp_path):
    current_path = tmp_path / "current_track.json"
    current_path.write_text("{bad json")
    monkeypatch.setattr(np_service, "current_track_json_file", lambda: current_path)
    monkeypatch.setattr(np_service, "sync", lambda source, idle_text: {"track": {"source": "apple_music", "state": "idle"}})
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
    monkeypatch.setattr(np_service, "read_previous_state", lambda: {})

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

    monkeypatch.setattr(np_service, "select_track", lambda source: make_track())

    obs_calls = []
    monkeypatch.setattr(np_service, "update_obs", lambda track, text: obs_calls.append((track.source, text)) or True)

    first = np_service.sync("auto", "")
    assert first["changed"] is True
    assert obs_calls == [("apple_music", '"Track"\nArtist\nAlbum')]

    monkeypatch.setattr(np_service, "read_previous_state", lambda: {
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
        "artwork_path": "",
    }
    server = np_service.NowPlayingHTTPServer(("127.0.0.1", 0), np_service.RequestHandler, lambda: payload)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("GET", "/health")
        health = json.loads(conn.getresponse().read().decode("utf-8"))
        assert health == {"status": "ok"}

        conn.request("GET", "/current")
        current = json.loads(conn.getresponse().read().decode("utf-8"))
        assert current["source"] == "spotify"

        conn.request("GET", "/current.txt")
        assert conn.getresponse().read().decode("utf-8") == ""

        conn.request("GET", "/artwork")
        artwork = json.loads(conn.getresponse().read().decode("utf-8"))
        assert artwork == {"artwork_path": ""}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


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

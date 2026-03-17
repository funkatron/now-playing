#!/usr/bin/env python3

import argparse
import json
import logging
import os
import plistlib
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional


LOGGER = logging.getLogger("now_playing")

PLAYING_STATE_CODE = 1800426320
DEFAULT_SOURCE = os.environ.get("NOW_PLAYING_SOURCE", "auto")
DEFAULT_IDLE_TEXT = os.environ.get("NOW_PLAYING_IDLE_TEXT", "")


@dataclass
class TrackInfo:
    source: str
    state: str
    title: str = ""
    artist: str = ""
    album: str = ""
    year: Optional[int] = None
    artwork_path: str = ""
    updated_at: str = ""

    def to_text(self, idle_text: str = DEFAULT_IDLE_TEXT) -> str:
        if self.state != "playing" or not self.title:
            return idle_text

        year = str(self.year) if self.year else ""
        return f"\"{self.title}\"\n{self.artist}\n{self.album}\n{year}".rstrip()

    def fingerprint(self) -> dict:
        return {
            "source": self.source,
            "state": self.state,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "year": self.year,
            "artwork_path": self.artwork_path,
        }


class ProviderError(RuntimeError):
    pass


def configure_logging() -> None:
    level_name = os.environ.get("PYTHON_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")


def safe_filename(value: str) -> str:
    return re.sub(r"[^\w-]", "", value)


def repo_dir() -> Path:
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    path = repo_dir() / "_data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = repo_dir() / "_logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_env_file() -> Path:
    return repo_dir() / "config.env"


def config_env_example_file() -> Path:
    return repo_dir() / "config.env.example"


def state_file() -> Path:
    return data_dir() / "sync_state.json"


def current_song_file() -> Path:
    return data_dir() / "current_song.txt"


def current_track_json_file() -> Path:
    return data_dir() / "current_track.json"


def artwork_manifest_file() -> Path:
    return data_dir() / "now_playing_artworks.txt"


def current_artwork_file() -> Path:
    return data_dir() / "current_artwork.png"


def write_text_if_changed(path: Path, content: str) -> bool:
    existing = path.read_text() if path.exists() else None
    if existing == content:
        return False

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content)
    tmp_path.replace(path)
    return True


def write_json_if_changed(path: Path, payload: dict) -> bool:
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    return write_text_if_changed(path, content)


def copy_file_if_changed(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False

    if destination.exists() and source.read_bytes() == destination.read_bytes():
        return False

    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copyfile(source, tmp_path)
    tmp_path.replace(destination)
    return True


def remove_file_if_exists(path: Path) -> bool:
    if path.exists():
        path.unlink()
        return True
    return False


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_config_env() -> None:
    path = config_env_file()
    if not path.exists():
        return

    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def read_previous_state() -> dict:
    path = state_file()
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        LOGGER.warning("Ignoring invalid state file at %s", path)
        return {}


def save_state(payload: dict) -> None:
    write_json_if_changed(state_file(), payload)


def extract_apple_music_artwork(track) -> str:
    from AppKit import NSBitmapImageRep, NSPNGFileType

    artworks = track.artworks()
    if not artworks:
        return ""

    cache_dir = Path.home() / ".now-playing" / "artwork-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_name = safe_filename(
        f"{track.databaseID()}_{track.artist()}_{track.album()}_{track.name()}"
    )
    cache_path = cache_dir / f"{cache_name}.png"

    first_artwork = artworks[0]
    if not first_artwork.data():
        return ""

    bitmap_rep = NSBitmapImageRep.imageRepWithData_(first_artwork.data().TIFFRepresentation())
    png_data = bitmap_rep.representationUsingType_properties_(NSPNGFileType, None)
    png_data.writeToFile_atomically_(str(cache_path), True)
    return str(cache_path)


def get_apple_music_track() -> TrackInfo:
    import ScriptingBridge

    music_app = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Music")
    if not music_app or not music_app.isRunning():
        return TrackInfo(source="apple_music", state="not_running", updated_at=iso_now())

    if music_app.playerState() != PLAYING_STATE_CODE:
        return TrackInfo(source="apple_music", state="idle", updated_at=iso_now())

    current_track = music_app.currentTrack()
    if current_track is None or not current_track.name():
        return TrackInfo(source="apple_music", state="idle", updated_at=iso_now())

    year = current_track.year()
    return TrackInfo(
        source="apple_music",
        state="playing",
        title=str(current_track.name() or ""),
        artist=str(current_track.artist() or ""),
        album=str(current_track.album() or ""),
        year=int(year) if year else None,
        artwork_path=extract_apple_music_artwork(current_track),
        updated_at=iso_now(),
    )


def get_spotify_track() -> TrackInfo:
    from ScriptingBridge import SBApplication

    spotify_app = SBApplication.applicationWithBundleIdentifier_("com.spotify.client")
    if not spotify_app or not spotify_app.isRunning():
        return TrackInfo(source="spotify", state="not_running", updated_at=iso_now())

    player_state = str(spotify_app.playerState() or "").lower()
    if player_state != "playing":
        return TrackInfo(source="spotify", state="idle", updated_at=iso_now())

    current_track = spotify_app.currentTrack()
    if current_track is None or not current_track.name():
        return TrackInfo(source="spotify", state="idle", updated_at=iso_now())

    return TrackInfo(
        source="spotify",
        state="playing",
        title=str(current_track.name() or ""),
        artist=str(current_track.artist() or ""),
        album=str(current_track.album() or ""),
        updated_at=iso_now(),
    )


def select_track(source: str) -> TrackInfo:
    if source == "apple_music":
        return get_apple_music_track()
    if source == "spotify":
        return get_spotify_track()
    if source != "auto":
        raise ProviderError(f"Unsupported source: {source}")

    apple_track = get_apple_music_track()
    if apple_track.state == "playing":
        return apple_track

    spotify_track = get_spotify_track()
    if spotify_track.state == "playing":
        return spotify_track

    if apple_track.state != "not_running":
        return apple_track

    return spotify_track


def obs_enabled() -> bool:
    return os.environ.get("OBSWS_ENABLED", "0") == "1"


def update_obs(track: TrackInfo, display_text: str) -> bool:
    if not obs_enabled():
        LOGGER.debug("Skipping OBS update because OBSWS_ENABLED is not set.")
        return False

    from obswebsocket import obsws, requests

    host = os.environ.get("OBSWS_HOST", "localhost")
    port = int(os.environ.get("OBSWS_PORT", "4455"))
    password = os.environ.get("OBSWS_PASSWORD", "")
    image_input = os.environ.get("OBSWS_IMAGE_INPUT_NAME", "NPImage")
    text_input = os.environ.get("OBSWS_TEXT_INPUT_NAME")
    text_field = os.environ.get("OBSWS_TEXT_FIELD", "text")

    ws = obsws(host, port, password)
    ws.connect()
    try:
        if track.artwork_path and current_artwork_file().exists():
            ws.call(
                requests.SetInputSettings(
                    inputName=image_input,
                    inputSettings={"file": str(current_artwork_file())},
                )
            )

        if text_input:
            ws.call(
                requests.SetInputSettings(
                    inputName=text_input,
                    inputSettings={text_field: display_text},
                )
            )
    finally:
        ws.disconnect()

    LOGGER.debug("Updated OBS for source=%s state=%s", track.source, track.state)
    return True


def materialize_outputs(track: TrackInfo, idle_text: str) -> dict:
    display_text = track.to_text(idle_text)
    artwork_changed = False
    if track.artwork_path:
        artwork_changed = copy_file_if_changed(Path(track.artwork_path), current_artwork_file())
        write_text_if_changed(artwork_manifest_file(), f"{current_artwork_file()}\n")
        track.artwork_path = str(current_artwork_file())
    else:
        artwork_changed = remove_file_if_exists(current_artwork_file()) or artwork_changed
        remove_file_if_exists(artwork_manifest_file())

    payload = asdict(track)
    payload["text"] = display_text

    text_changed = write_text_if_changed(current_song_file(), display_text)
    json_changed = write_json_if_changed(current_track_json_file(), payload)

    return {
        "payload": payload,
        "display_text": display_text,
        "text_changed": text_changed,
        "json_changed": json_changed,
        "artwork_changed": artwork_changed,
    }


def sync(source: str, idle_text: str) -> dict:
    track = select_track(source)
    previous = read_previous_state()

    outputs = materialize_outputs(track, idle_text)
    payload = outputs["payload"]

    normalized_track = dict(track.fingerprint())
    normalized_track["artwork_path"] = payload["artwork_path"]

    track_changed = previous.get("track") != normalized_track
    obs_updated = False
    if track_changed or outputs["artwork_changed"]:
        obs_updated = update_obs(track, outputs["display_text"])

    save_state(
        {
            "track": normalized_track,
            "artwork_path": payload["artwork_path"],
            "updated_at": payload["updated_at"],
        }
    )

    return {
        "track": payload,
        "changed": track_changed,
        "text_changed": outputs["text_changed"],
        "json_changed": outputs["json_changed"],
        "artwork_changed": outputs["artwork_changed"],
        "obs_updated": obs_updated,
    }


def read_current_payload(idle_text: str) -> dict:
    if current_track_json_file().exists():
        try:
            return json.loads(current_track_json_file().read_text())
        except json.JSONDecodeError:
            LOGGER.warning("Current track file is invalid; regenerating from live state.")

    result = sync(DEFAULT_SOURCE, idle_text)
    return result["track"]


class NowPlayingHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, current_payload_getter):
        super().__init__(server_address, handler_class)
        self.current_payload_getter = current_payload_getter


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "NowPlayingHTTP/1.0"

    def do_GET(self) -> None:
        if self.path == "/health":
            self.respond_json({"status": "ok"})
            return

        payload = self.server.current_payload_getter()
        if self.path == "/current":
            self.respond_json(payload)
            return

        if self.path == "/current.txt":
            self.respond_text(payload.get("text", ""))
            return

        if self.path == "/artwork":
            self.respond_json({"artwork_path": payload.get("artwork_path", "")})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, fmt: str, *args) -> None:
        LOGGER.debug("HTTP %s - %s", self.address_string(), fmt % args)

    def respond_json(self, payload: dict) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_text(self, body: str) -> None:
        content = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run_server(source: str, idle_text: str, host: str, port: int, interval_seconds: float) -> int:
    current_payload = {"text": idle_text}
    payload_lock = threading.Lock()
    stop_event = threading.Event()

    def refresh_once() -> None:
        nonlocal current_payload
        result = sync(source, idle_text)
        with payload_lock:
            current_payload = result["track"]

    def refresh_loop() -> None:
        nonlocal current_payload
        while not stop_event.is_set():
            try:
                refresh_once()
            except Exception:
                LOGGER.exception("Sync loop failed")
            stop_event.wait(interval_seconds)

    def get_payload() -> dict:
        with payload_lock:
            return dict(current_payload)

    refresh_once()
    worker = threading.Thread(target=refresh_loop, name="sync-loop", daemon=True)
    worker.start()

    server = NowPlayingHTTPServer((host, port), RequestHandler, get_payload)
    LOGGER.info("Serving now playing API on http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopping server")
    finally:
        stop_event.set()
        server.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Now Playing utility")
    parser.add_argument("--source", choices=["auto", "apple_music", "spotify"])
    parser.add_argument("--idle-text")

    subparsers = parser.add_subparsers(dest="command")

    current_parser = subparsers.add_parser("current", help="Get the current track")
    current_parser.add_argument("--format", default="json", choices=["json", "text"])

    subparsers.add_parser("artwork", help="Get the current artwork path")
    subparsers.add_parser("sync", help="Sync track data to files and OBS")

    serve_parser = subparsers.add_parser("serve", help="Run the polling daemon and local HTTP API")
    serve_parser.add_argument("--host", default=os.environ.get("NOW_PLAYING_HOST", "127.0.0.1"))
    serve_parser.add_argument("--port", type=int, default=int(os.environ.get("NOW_PLAYING_PORT", "8976")))
    serve_parser.add_argument(
        "--interval-seconds",
        type=float,
        default=float(os.environ.get("INTERVAL_SECONDS", "5")),
    )

    subparsers.add_parser("init-config", help="Create config.env from config.env.example if missing")
    subparsers.add_parser("install-service", help="Install and start the launchd service")
    subparsers.add_parser("uninstall-service", help="Stop and remove the launchd service")

    return parser


def current_settings(args: argparse.Namespace) -> tuple[str, str]:
    source = args.source or os.environ.get("NOW_PLAYING_SOURCE", DEFAULT_SOURCE)
    idle_text = args.idle_text if args.idle_text is not None else os.environ.get("NOW_PLAYING_IDLE_TEXT", DEFAULT_IDLE_TEXT)
    return source, idle_text


def launch_agent_label() -> str:
    return os.environ.get("NOW_PLAYING_LAUNCHD_LABEL", "com.funkatron.now-playing")


def launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{launch_agent_label()}.plist"


def env_subset() -> dict:
    keys = [
        "NOW_PLAYING_SOURCE",
        "NOW_PLAYING_IDLE_TEXT",
        "NOW_PLAYING_HOST",
        "NOW_PLAYING_PORT",
        "INTERVAL_SECONDS",
        "PYTHON_LOG_LEVEL",
        "OBSWS_ENABLED",
        "OBSWS_HOST",
        "OBSWS_PORT",
        "OBSWS_PASSWORD",
        "OBSWS_IMAGE_INPUT_NAME",
        "OBSWS_TEXT_INPUT_NAME",
        "OBSWS_TEXT_FIELD",
    ]
    return {key: os.environ[key] for key in keys if key in os.environ}


def init_config() -> int:
    destination = config_env_file()
    if destination.exists():
        print(destination)
        return 0

    shutil.copyfile(config_env_example_file(), destination)
    print(destination)
    return 0


def install_service() -> int:
    logs_dir()
    data_dir()
    launch_agent_path().parent.mkdir(parents=True, exist_ok=True)

    plist_payload = {
        "Label": launch_agent_label(),
        "WorkingDirectory": str(repo_dir()),
        "ProgramArguments": [sys.executable, str(repo_dir() / "np_service.py"), "serve"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(logs_dir() / "launchd.log"),
        "StandardErrorPath": str(logs_dir() / "launchd.log"),
        "EnvironmentVariables": env_subset(),
    }

    launch_agent_path().write_bytes(plistlib.dumps(plist_payload))

    domain = f"gui/{os.getuid()}"
    label_ref = f"{domain}/{launch_agent_label()}"
    subprocess.run(["launchctl", "bootout", label_ref], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["launchctl", "bootstrap", domain, str(launch_agent_path())], check=True)
    subprocess.run(["launchctl", "enable", label_ref], check=True)
    subprocess.run(["launchctl", "kickstart", "-k", label_ref], check=True)

    host = os.environ.get("NOW_PLAYING_HOST", "127.0.0.1")
    port = os.environ.get("NOW_PLAYING_PORT", "8976")
    print(f"Installed {launch_agent_label()} and started http://{host}:{port}/current")
    return 0


def uninstall_service() -> int:
    domain = f"gui/{os.getuid()}"
    label_ref = f"{domain}/{launch_agent_label()}"
    subprocess.run(["launchctl", "bootout", label_ref], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if launch_agent_path().exists():
        launch_agent_path().unlink()
    print(f"Removed {launch_agent_label()}")
    return 0


def main(argv: list[str]) -> int:
    load_config_env()
    configure_logging()
    logs_dir()
    parser = build_parser()
    args = parser.parse_args(argv)

    command = args.command or "current"
    source, idle_text = current_settings(args)

    if command == "current":
        track = select_track(source)
        if args.format == "text":
            print(track.to_text(idle_text))
        else:
            print(json.dumps(asdict(track), indent=2, sort_keys=True))
        return 0

    if command == "artwork":
        track = select_track(source)
        if track.artwork_path:
            print(track.artwork_path)
        return 0

    if command == "sync":
        result = sync(source, idle_text)
        LOGGER.info(
            "Sync complete: source=%s state=%s changed=%s obs_updated=%s",
            result["track"]["source"],
            result["track"]["state"],
            result["changed"],
            result["obs_updated"],
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if command == "serve":
        return run_server(source, idle_text, args.host, args.port, args.interval_seconds)

    if command == "init-config":
        return init_config()

    if command == "install-service":
        return install_service()

    if command == "uninstall-service":
        return uninstall_service()

    parser.print_help()
    return 1


def cli() -> int:
    return main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(cli())

#!/usr/bin/env python3

import argparse
import json
import logging
import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


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


@dataclass
class ProviderSnapshot:
    source: str
    state: str
    detail: str = ""
    error: Optional[str] = None
    updated_at: str = ""

    def to_payload(self) -> dict:
        return {
            "source": self.source,
            "state": self.state,
            "detail": self.detail,
            "error": self.error,
            "updated_at": self.updated_at,
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


def spotify_session_pid_file() -> Path:
    return data_dir() / "spotify-session.pid"


def namespaced_state_file(namespace: str = "current") -> Path:
    if namespace == "spotify":
        return data_dir() / "spotify_sync_state.json"
    return state_file()


def namespaced_current_song_file(namespace: str = "current") -> Path:
    if namespace == "spotify":
        return data_dir() / "spotify_current_song.txt"
    return current_song_file()


def namespaced_current_track_json_file(namespace: str = "current") -> Path:
    if namespace == "spotify":
        return data_dir() / "spotify_current_track.json"
    return current_track_json_file()


def namespaced_artwork_manifest_file(namespace: str = "current") -> Path:
    if namespace == "spotify":
        return data_dir() / "spotify_now_playing_artworks.txt"
    return artwork_manifest_file()


def namespaced_current_artwork_file(namespace: str = "current") -> Path:
    if namespace == "spotify":
        return data_dir() / "spotify_current_artwork.png"
    return current_artwork_file()


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


def is_playing_state(player_state) -> bool:
    if player_state == PLAYING_STATE_CODE:
        return True

    if isinstance(player_state, str):
        return player_state.strip().lower() == "playing"

    return str(player_state or "").strip().lower() == "playing"


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


def read_previous_state(namespace: str = "current") -> dict:
    path = namespaced_state_file(namespace)
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        LOGGER.warning("Ignoring invalid state file at %s", path)
        return {}


def save_state(payload: dict, namespace: str = "current") -> None:
    write_json_if_changed(namespaced_state_file(namespace), payload)


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
    artwork_data = first_artwork.data()
    if not artwork_data:
        return ""

    if hasattr(artwork_data, "TIFFRepresentation"):
        raw_data = artwork_data.TIFFRepresentation()
    elif hasattr(artwork_data, "NSRepresentation"):
        raw_data = artwork_data.NSRepresentation()
    else:
        raw_data = artwork_data

    bitmap_rep = NSBitmapImageRep.imageRepWithData_(raw_data)
    if bitmap_rep is None:
        LOGGER.debug("Apple Music artwork data could not be converted to NSBitmapImageRep.")
        return ""

    png_data = bitmap_rep.representationUsingType_properties_(NSPNGFileType, None)
    if png_data is None:
        LOGGER.debug("Apple Music artwork data could not be converted to PNG.")
        return ""

    png_data.writeToFile_atomically_(str(cache_path), True)
    return str(cache_path)


def spotify_artwork_cache_path(title: str, artist: str, album: str, artwork_url: str) -> Path:
    cache_dir = Path.home() / ".now-playing" / "artwork-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    parsed = urllib.parse.urlparse(artwork_url)
    _root, ext = os.path.splitext(parsed.path)
    if not ext:
        ext = ".jpg"
    cache_name = safe_filename(f"spotify_{artist}_{album}_{title}")
    return cache_dir / f"{cache_name}{ext}"


def fetch_spotify_artwork(title: str, artist: str, album: str, artwork_url: str) -> str:
    if not artwork_url:
        return ""

    cache_path = spotify_artwork_cache_path(title, artist, album, artwork_url)
    if cache_path.exists():
        return str(cache_path)

    try:
        req = urllib.request.Request(artwork_url, headers={"User-Agent": "now-playing/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response, cache_path.open("wb") as output:
            output.write(response.read())
    except Exception as exc:  # pragma: no cover - best effort
        LOGGER.debug("Spotify artwork download failed: %s", exc)
        return ""

    return str(cache_path)


def run_osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def spotify_query_script() -> str:
    return """
tell application "Spotify"
    if it is not running then return "not_running"
    set outputParts to {}
    set end of outputParts to (player state as text)
    if player state is playing then
        set end of outputParts to (name of current track as text)
        set end of outputParts to (artist of current track as text)
        set end of outputParts to (album of current track as text)
        set end of outputParts to (artwork url of current track as text)
    end if
    set AppleScript's text item delimiters to (character id 31)
    return outputParts as text
end tell
"""


def query_spotify_snapshot() -> list[str]:
    output = run_osascript(spotify_query_script())
    return output.split(chr(31)) if output else []


def spotify_state(snapshot: list[str]) -> str:
    if not snapshot:
        return "not_running"
    return snapshot[0].strip().lower()


def spotify_track_fields(snapshot: list[str]) -> tuple[str, str, str, str]:
    if len(snapshot) < 5:
        return "", "", "", ""
    return tuple(part.strip() for part in snapshot[1:5])


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
    try:
        snapshot = query_spotify_snapshot()
    except subprocess.CalledProcessError as exc:
        LOGGER.debug("Spotify AppleScript query failed: %s", exc)
        return TrackInfo(source="spotify", state="not_running", updated_at=iso_now())

    player_state = spotify_state(snapshot)
    LOGGER.debug("Spotify AppleScript player state: %r", player_state)
    if player_state != "playing":
        state = "not_running" if player_state == "not_running" else "idle"
        return TrackInfo(source="spotify", state=state, updated_at=iso_now())

    title, artist, album, artwork_url = spotify_track_fields(snapshot)
    if not title:
        return TrackInfo(source="spotify", state="idle", updated_at=iso_now())

    return TrackInfo(
        source="spotify",
        state="playing",
        title=title,
        artist=artist,
        album=album,
        artwork_path=fetch_spotify_artwork(title, artist, album, artwork_url),
        updated_at=iso_now(),
    )


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


def materialize_outputs(track: TrackInfo, idle_text: str, namespace: str = "current") -> dict:
    display_text = track.to_text(idle_text)
    artwork_changed = False
    if track.artwork_path:
        artwork_file = namespaced_current_artwork_file(namespace)
        artwork_changed = copy_file_if_changed(Path(track.artwork_path), artwork_file)
        write_text_if_changed(namespaced_artwork_manifest_file(namespace), f"{artwork_file}\n")
        track.artwork_path = str(artwork_file)
    else:
        artwork_changed = remove_file_if_exists(namespaced_current_artwork_file(namespace)) or artwork_changed
        remove_file_if_exists(namespaced_artwork_manifest_file(namespace))

    payload = asdict(track)
    payload["text"] = display_text

    text_changed = write_text_if_changed(namespaced_current_song_file(namespace), display_text)

    return {
        "payload": payload,
        "display_text": display_text,
        "text_changed": text_changed,
        "artwork_changed": artwork_changed,
    }


def sync(source: str, idle_text: str, namespace: str = "current") -> dict:
    track, providers = select_track_with_diagnostics(source)
    previous = read_previous_state(namespace)

    outputs = materialize_outputs(track, idle_text, namespace)
    payload = outputs["payload"]
    payload["providers"] = providers

    normalized_track = dict(track.fingerprint())
    normalized_track["artwork_path"] = payload["artwork_path"]

    track_changed = previous.get("track") != normalized_track
    if not track_changed and previous.get("updated_at"):
        payload["updated_at"] = previous["updated_at"]

    json_changed = write_json_if_changed(namespaced_current_track_json_file(namespace), payload)

    obs_updated = False
    if track_changed or outputs["artwork_changed"]:
        obs_updated = update_obs(track, outputs["display_text"])

    save_state(
        {
            "track": normalized_track,
            "artwork_path": payload["artwork_path"],
            "updated_at": payload["updated_at"],
            "providers": providers,
        },
        namespace,
    )

    return {
        "track": payload,
        "changed": track_changed,
        "text_changed": outputs["text_changed"],
        "json_changed": json_changed,
        "artwork_changed": outputs["artwork_changed"],
        "obs_updated": obs_updated,
    }


def empty_payload(source: str = "unknown") -> dict:
    return {
        "album": "",
        "artist": "",
        "artwork_path": None,
        "providers": {
            source: {
                "detail": "",
                "error": None,
                "source": source,
                "state": "not_running",
                "updated_at": iso_now(),
            }
        } if source != "unknown" else {},
        "source": source,
        "state": "not_running",
        "text": "",
        "title": "",
        "updated_at": iso_now(),
        "year": None,
    }


def read_current_payload(idle_text: str, namespace: str = "current", live_fallback: bool = True) -> dict:
    path = namespaced_current_track_json_file(namespace)
    if path.exists():
        try:
            payload = json.loads(path.read_text())
            if payload.get("artwork_path", "") == "":
                payload["artwork_path"] = None
            return payload
        except json.JSONDecodeError:
            LOGGER.warning("Current track file is invalid; regenerating from live state.")

    if not live_fallback:
        source = "spotify" if namespace == "spotify" else "unknown"
        return empty_payload(source)

    result = sync(DEFAULT_SOURCE, idle_text, namespace)
    return result["track"]


class NowPlayingHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, current_payload_getter):
        super().__init__(server_address, handler_class)
        self.current_payload_getter = current_payload_getter
        self.event_clients: set = set()
        self.event_clients_lock = threading.Lock()

    def add_event_client(self, handler) -> None:
        with self.event_clients_lock:
            self.event_clients.add(handler)

    def remove_event_client(self, handler) -> None:
        with self.event_clients_lock:
            self.event_clients.discard(handler)

    def broadcast_event(self, payload: dict) -> None:
        message = f"event: now_playing\ndata: {json.dumps(payload, sort_keys=True)}\n\n".encode("utf-8")
        with self.event_clients_lock:
            clients = list(self.event_clients)

        stale_clients = []
        for client in clients:
            try:
                client.wfile.write(message)
                client.wfile.flush()
            except Exception:
                stale_clients.append(client)

        if stale_clients:
            with self.event_clients_lock:
                for client in stale_clients:
                    self.event_clients.discard(client)


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "NowPlayingHTTP/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.respond_html(self.render_dashboard("/", True))
            return

        if parsed.path == "/spotify/" or parsed.path == "/spotify":
            self.respond_html(self.render_dashboard("/spotify", False))
            return

        if parsed.path == "/events":
            self.respond_events()
            return

        if parsed.path == "/health":
            self.respond_json({"status": "ok"})
            return

        payload = self.server.current_payload_getter()
        if parsed.path == "/current":
            self.respond_json(payload)
            return

        if parsed.path == "/current.txt":
            self.respond_text(payload.get("text", ""))
            return

        if parsed.path == "/artwork":
            self.respond_json({"artwork_path": payload.get("artwork_path") or None})
            return

        if parsed.path == "/current_artwork.png":
            self.respond_artwork("current")
            return

        if parsed.path == "/spotify/current":
            self.respond_json(read_current_payload("", "spotify", live_fallback=False))
            return

        if parsed.path == "/spotify/current.txt":
            spotify_payload = read_current_payload("", "spotify", live_fallback=False)
            self.respond_text(spotify_payload.get("text", ""))
            return

        if parsed.path == "/spotify/artwork":
            spotify_payload = read_current_payload("", "spotify", live_fallback=False)
            self.respond_json({"artwork_path": spotify_payload.get("artwork_path") or None})
            return

        if parsed.path == "/spotify/current_artwork.png":
            self.respond_artwork("spotify")
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, fmt: str, *args) -> None:
        LOGGER.debug("HTTP %s - %s", self.address_string(), fmt % args)

    def render_dashboard(self, route_prefix: str, use_sse: bool) -> str:
        html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Now Playing</title>
  <style>
    :root {
      --bg: #060709;
      --bg-2: #11161b;
      --panel: rgba(10, 12, 15, 0.84);
      --panel-edge: rgba(255, 255, 255, 0.08);
      --text: #f4efe4;
      --muted: #aea79b;
      --soft: #7e7a73;
      --accent: #c7462d;
      --accent-soft: rgba(199, 70, 45, 0.2);
      --glow: rgba(199, 70, 45, 0.16);
      --art-bg: linear-gradient(145deg, #191b1f, #08090b);
      --font-iosevka:
        "Iosevka Aile",
        "Iosevka Etoile",
        "Iosevka Curly",
        "Iosevka Curly Slab",
        "Iosevka Slab",
        "Iosevka Term",
        "Iosevka Fixed",
        "Iosevka",
        "Iosevka Nerd Font",
        "IosevkaTerm Nerd Font",
        "IosevkaTerm NFM",
        "Iosevka NFM",
        monospace;
    }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top left, rgba(199, 70, 45, 0.18), transparent 28%),
        radial-gradient(circle at 85% 20%, rgba(73, 86, 104, 0.2), transparent 24%),
        linear-gradient(160deg, var(--bg) 0%, #0d1116 46%, #13181f 100%);
      color: var(--text);
      font-family: var(--font-iosevka);
      overflow-x: hidden;
      overflow-y: auto;
    }
    body, button, input, textarea, select {
      font-family: var(--font-iosevka);
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0.01)),
        repeating-linear-gradient(
          180deg,
          transparent 0,
          transparent 3px,
          rgba(255, 255, 255, 0.015) 4px
        );
      mix-blend-mode: soft-light;
      opacity: 0.55;
    }
    .shell {
      min-height: 100vh;
      display: grid;
      align-items: start;
      justify-items: center;
      padding: clamp(18px, 4vh, 40px) 20px 24px;
      box-sizing: border-box;
    }
    .card {
      position: relative;
      width: min(1120px, calc(100vw - 40px));
      border-radius: 30px;
      padding: 24px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.04), transparent 18%),
        var(--panel);
      border: 1px solid var(--panel-edge);
      box-shadow:
        0 38px 90px rgba(0, 0, 0, 0.55),
        0 0 0 1px rgba(255, 255, 255, 0.03) inset,
        0 0 90px var(--glow);
      backdrop-filter: blur(14px);
    }
    .card::before {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      padding: 1px;
      background: linear-gradient(135deg, rgba(199, 70, 45, 0.55), transparent 35%, rgba(255,255,255,0.08));
      -webkit-mask:
        linear-gradient(#fff 0 0) content-box,
        linear-gradient(#fff 0 0);
      -webkit-mask-composite: xor;
      mask-composite: exclude;
      pointer-events: none;
      opacity: 0.7;
    }
    .masthead {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 18px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 11px;
      color: var(--muted);
    }
    .brand {
      display: inline-flex;
      gap: 10px;
      align-items: center;
    }
    .brand-mark {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 18px rgba(199, 70, 45, 0.7);
    }
    .brand-copy {
      display: flex;
      gap: 10px;
      align-items: baseline;
    }
    .brand-copy strong {
      color: var(--text);
      font-weight: 700;
    }
    .signal {
      display: inline-flex;
      gap: 8px;
      align-items: center;
      color: var(--soft);
    }
    .grid {
      display: grid;
      gap: 22px;
      grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
      align-items: stretch;
    }
    .artwork {
      aspect-ratio: 1;
      border-radius: 24px;
      overflow: hidden;
      background: var(--art-bg);
      display: grid;
      place-items: center;
      border: 1px solid rgba(255, 255, 255, 0.06);
      box-shadow:
        inset 0 0 0 1px rgba(255,255,255,0.03),
        0 20px 50px rgba(0, 0, 0, 0.35);
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 11px;
      position: relative;
    }
    .artwork::after {
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.08), transparent 24%),
        linear-gradient(135deg, transparent 45%, rgba(199, 70, 45, 0.14));
      pointer-events: none;
    }
    .artwork img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: none;
    }
    .content {
      display: flex;
      flex-direction: column;
      justify-content: center;
      min-width: 0;
      padding-right: 8px;
    }
    .kicker {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.22em;
      font-size: 12px;
    }
    .title {
      margin-top: 12px;
      font-size: clamp(40px, 6vw, 84px);
      line-height: 0.9;
      font-weight: 800;
      font-family: var(--font-iosevka);
      letter-spacing: -0.08em;
      text-wrap: balance;
    }
    .meta {
      margin-top: 10px;
      color: #d8d1c2;
      font-size: clamp(18px, 2vw, 24px);
      max-width: 30ch;
    }
    .status-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-top: 18px;
    }
    .status {
      display: inline-flex;
      padding: 9px 14px;
      border-radius: 999px;
      background: rgba(255,255,255,0.06);
      color: var(--text);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      border: 1px solid rgba(255,255,255,0.08);
    }
    .state-playing {
      background: var(--accent-soft);
      border-color: rgba(199, 70, 45, 0.35);
      color: #ffd6cf;
    }
    .state-idle, .state-not_running {
      color: var(--muted);
    }
    .details {
      display: grid;
      gap: 12px;
      margin-top: 20px;
      grid-template-columns: repeat(2, minmax(180px, 1fr));
    }
    .detail {
      padding-top: 12px;
      border-top: 1px solid rgba(255,255,255,0.08);
    }
    .detail-label {
      display: block;
      color: var(--soft);
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 10px;
      margin-bottom: 6px;
    }
    .detail-value {
      color: var(--text);
      font-size: 15px;
      word-break: break-word;
      overflow-wrap: anywhere;
      font-family: var(--font-iosevka);
    }
    .masthead,
    .brand,
    .brand-copy,
    .signal,
    .kicker,
    .meta,
    .status,
    .detail-label,
    .detail-value,
    .footer-note {
      font-family: var(--font-iosevka);
    }
    .footer-note {
      margin-top: 18px;
      color: var(--soft);
      font-size: 12px;
      letter-spacing: 0.06em;
    }
    .providers {
      display: grid;
      gap: 10px;
      margin-top: 18px;
    }
    .provider-card {
      padding: 12px 14px;
      border-radius: 14px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
    }
    .provider-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      margin-bottom: 6px;
    }
    .provider-name {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-size: 11px;
    }
    .provider-state {
      color: var(--text);
      font-size: 13px;
      text-transform: uppercase;
    }
    .provider-detail {
      color: var(--soft);
      font-size: 12px;
      line-height: 1.45;
    }
    .provider-error {
      color: #ffb4a5;
    }
    @media (max-width: 960px) {
      .grid {
        grid-template-columns: 1fr;
        gap: 22px;
      }
      .content {
        padding-right: 0;
      }
      .details {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 680px) {
      .shell {
        padding: 14px;
      }
      .card {
        padding: 16px;
        border-radius: 22px;
      }
      .masthead {
        margin-bottom: 14px;
      }
      .title {
        font-size: clamp(34px, 11vw, 56px);
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <main class="card">
      <div class="masthead">
        <div class="brand">
          <span class="brand-mark"></span>
          <div class="brand-copy">
            <strong>Funkatron</strong>
            <span>/ Dead Agent signal</span>
          </div>
        </div>
        <div class="signal">Local viewer / SSE live feed</div>
      </div>
      <div class="grid">
        <div class="artwork">
          <img id="artwork-image" alt="Current artwork">
          <div id="artwork-empty">No Artwork</div>
        </div>
        <section class="content">
          <div class="kicker">Now Playing</div>
          <div id="title" class="title">Waiting for playback</div>
          <div id="meta" class="meta">Start Apple Music or Spotify and press play.</div>
          <div class="status-row">
            <div id="status" class="status">idle</div>
          </div>
          <div class="details">
            <div class="detail">
              <span class="detail-label">Source</span>
              <span id="source" class="detail-value">unknown</span>
            </div>
            <div class="detail">
              <span class="detail-label">Updated</span>
              <span id="updated-at" class="detail-value">never</span>
            </div>
          </div>
          <div id="providers" class="providers"></div>
          <div class="footer-note">Live local feed for stream overlays, OBS, and operator checks.</div>
        </section>
      </div>
    </main>
  </div>
  <script>
    const endpointPrefix = "__ENDPOINT_PREFIX__";
    const useSse = __USE_SSE__;
    const titleEl = document.getElementById("title");
    const metaEl = document.getElementById("meta");
    const statusEl = document.getElementById("status");
    const sourceEl = document.getElementById("source");
    const updatedAtEl = document.getElementById("updated-at");
    const artworkImageEl = document.getElementById("artwork-image");
    const artworkEmptyEl = document.getElementById("artwork-empty");
    const providersEl = document.getElementById("providers");
    let lastArtworkVersion = "";

    function endpoint(path) {
      return endpointPrefix + path;
    }

    function formatProviderName(name) {
      if (name === "apple_music") return "Apple Music";
      if (name === "spotify") return "Spotify";
      return name || "Unknown";
    }

    function renderProviders(payload) {
      const providers = payload.providers || {};
      const entries = Object.entries(providers);
      if (!entries.length) {
        providersEl.innerHTML = "";
        return;
      }

      providersEl.innerHTML = entries.map(([name, info]) => {
        const detailClass = info.error ? "provider-detail provider-error" : "provider-detail";
        const detail = info.error || info.detail || "No additional detail";
        return `
          <div class="provider-card">
            <div class="provider-head">
              <span class="provider-name">${formatProviderName(name)}</span>
              <span class="provider-state">${info.state || "unknown"}</span>
            </div>
            <div class="${detailClass}">${detail}</div>
          </div>
        `;
      }).join("");
    }

    function render(payload) {
      sourceEl.textContent = payload.source || "unknown";
      updatedAtEl.textContent = payload.updated_at || "never";
      statusEl.textContent = payload.state || "unknown";
      statusEl.className = "status state-" + (payload.state || "unknown");
      renderProviders(payload);

      if (payload.state === "playing" && payload.title) {
        titleEl.textContent = payload.title;
        const parts = [payload.artist, payload.album, payload.year].filter(Boolean);
        metaEl.textContent = parts.join(" • ") || "Playing";
      } else {
        titleEl.textContent = "Waiting for playback";
        metaEl.textContent = "Start Apple Music or Spotify and press play.";
      }

      if (payload.artwork_path) {
        const version = payload.updated_at || payload.artwork_path;
        if (version !== lastArtworkVersion) {
          artworkImageEl.src = endpoint("/current_artwork.png") + "?v=" + encodeURIComponent(version);
          lastArtworkVersion = version;
        }
        artworkImageEl.style.display = "block";
        artworkEmptyEl.style.display = "none";
      } else {
        lastArtworkVersion = "";
        artworkImageEl.removeAttribute("src");
        artworkImageEl.style.display = "none";
        artworkEmptyEl.style.display = "block";
      }
    }

    async function fetchCurrent() {
      const response = await fetch(endpoint("/current"), { cache: "no-store" });
      if (!response.ok) {
        throw new Error("current fetch failed");
      }
      render(await response.json());
    }

    fetchCurrent().catch(() => {
      statusEl.textContent = "disconnected";
    });

    if (useSse) {
      const events = new EventSource(endpoint("/events"));
      events.addEventListener("now_playing", (event) => {
        render(JSON.parse(event.data));
      });
      events.onerror = () => {
        statusEl.textContent = "disconnected";
      };
    } else {
      setInterval(() => {
        fetchCurrent().catch(() => {
          statusEl.textContent = "disconnected";
        });
      }, 5000);
    }
  </script>
</body>
</html>"""
        return html.replace("__ENDPOINT_PREFIX__", route_prefix).replace("__USE_SSE__", "true" if use_sse else "false")

    def respond_json(self, payload: dict) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_html(self, body: str) -> None:
        content = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def respond_text(self, body: str) -> None:
        content = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def respond_artwork(self, namespace: str = "current") -> None:
        path = namespaced_current_artwork_file(namespace)
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Artwork not found")
            return

        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def respond_events(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        self.server.add_event_client(self)
        initial_payload = self.server.current_payload_getter()
        self.wfile.write(
            f"event: now_playing\ndata: {json.dumps(initial_payload, sort_keys=True)}\n\n".encode("utf-8")
        )
        self.wfile.flush()

        try:
            while True:
                time.sleep(60)
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except Exception:
            pass
        finally:
            self.server.remove_event_client(self)


def run_server(source: str, idle_text: str, host: str, port: int, interval_seconds: float) -> int:
    current_payload = {"text": idle_text}
    payload_lock = threading.Lock()
    stop_event = threading.Event()
    server: NowPlayingHTTPServer | None = None

    def refresh_once() -> None:
        nonlocal current_payload
        result = sync(source, idle_text)
        payload = result["track"]
        with payload_lock:
            previous_payload = dict(current_payload)
            current_payload = payload
        if server and previous_payload != payload:
            server.broadcast_event(payload)

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

    spotify_session_parser = subparsers.add_parser(
        "start-spotify-session",
        help="Launch a Spotify-pinned service in Terminal or iTerm",
    )
    spotify_session_parser.add_argument(
        "--interval-seconds",
        type=float,
        default=float(os.environ.get("INTERVAL_SECONDS", "5")),
    )
    spotify_session_parser.add_argument(
        "--terminal",
        choices=["auto", "iterm", "terminal"],
        default=os.environ.get("NOW_PLAYING_SPOTIFY_TERMINAL", "auto"),
    )
    hidden_spotify_parser = subparsers.add_parser(
        "spotify-session-serve",
        help="Internal: run the Spotify terminal session server",
    )
    hidden_spotify_parser.add_argument(
        "--interval-seconds",
        type=float,
        default=float(os.environ.get("INTERVAL_SECONDS", "5")),
    )
    subparsers.add_parser("stop-spotify-session", help="Stop the Spotify terminal session if it is running")

    subparsers.add_parser("init-config", help="Create config.env from config.env.example if missing")
    subparsers.add_parser("install-service", help="Install and start the launchd service")
    subparsers.add_parser("start-service", help="Start the installed launchd service")
    subparsers.add_parser("stop-service", help="Stop the installed launchd service without removing it")
    subparsers.add_parser("restart-service", help="Restart the installed launchd service")
    subparsers.add_parser("status", help="Show launchd service status")
    tail_parser = subparsers.add_parser("tail", help="Show the launchd log")
    tail_parser.add_argument("--lines", type=int, default=40, help="Number of log lines to show")
    tail_parser.add_argument("--follow", action="store_true", help="Follow the log output")
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


def service_is_loaded(label_ref: str) -> bool:
    result = subprocess.run(
        ["launchctl", "print", label_ref],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def launchctl_domain() -> str:
    return f"gui/{os.getuid()}"


def launchctl_label_ref() -> str:
    return f"{launchctl_domain()}/{launch_agent_label()}"


def service_is_installed() -> bool:
    return launch_agent_path().exists()


def launchctl_print_lines(label_ref: str) -> list[str]:
    result = subprocess.run(
        ["launchctl", "print", label_ref],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def service_pid(label_ref: str) -> Optional[int]:
    for line in launchctl_print_lines(label_ref):
        stripped = line.strip()
        if stripped.startswith("pid = "):
            value = stripped.removeprefix("pid = ").strip()
            try:
                return int(value)
            except ValueError:
                return None
    return None


def service_http_url() -> str:
    host = os.environ.get("NOW_PLAYING_HOST", "127.0.0.1")
    port = os.environ.get("NOW_PLAYING_PORT", "8976")
    return f"http://{host}:{port}/"


def spotify_session_is_running() -> bool:
    pid_path = spotify_session_pid_file()
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, OSError):
        remove_file_if_exists(pid_path)
        return False


def detect_terminal_app(preference: str) -> str:
    if preference in {"iterm", "terminal"}:
        return preference

    if Path("/Applications/iTerm.app").exists():
        return "iterm"
    return "terminal"


def spotify_session_command(interval_seconds: float) -> str:
    return " ".join(
        [
            "cd",
            shlex.quote(str(repo_dir())),
            "&&",
            "uv",
            "run",
            "np",
            "spotify-session-serve",
            "--interval-seconds",
            shlex.quote(str(interval_seconds)),
        ]
    )


def launch_terminal_session(command: str, terminal: str) -> None:
    if terminal == "iterm":
        script = f'''
tell application "iTerm"
    activate
    if (count of windows) = 0 then
        create window with default profile
    end if
    tell current window
        create tab with default profile
        tell current session
            write text {json.dumps(command)}
        end tell
    end tell
end tell
'''
    else:
        script = f'''
tell application "Terminal"
    activate
    do script {json.dumps(command)}
end tell
'''
    run_osascript(script)


def start_spotify_session(interval_seconds: float, terminal_preference: str) -> int:
    if spotify_session_is_running():
        print(f"Spotify session is already running with PID {spotify_session_pid_file().read_text().strip()}")
        return 0

    terminal = detect_terminal_app(terminal_preference)
    command = spotify_session_command(interval_seconds)
    launch_terminal_session(command, terminal)
    print(f"Launched Spotify session in {terminal}; view it at {service_http_url()}spotify/")
    return 0


def run_spotify_session(interval_seconds: float, idle_text: str) -> int:
    pid_path = spotify_session_pid_file()
    pid_path.write_text(str(os.getpid()))
    try:
        while True:
            try:
                result = sync("spotify", idle_text, "spotify")
                LOGGER.info(
                    "Spotify session sync: state=%s changed=%s",
                    result["track"]["state"],
                    result["changed"],
                )
            except Exception:
                LOGGER.exception("Spotify session sync failed")
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        LOGGER.info("Stopping Spotify session")
        return 0
    finally:
        remove_file_if_exists(pid_path)


def stop_spotify_session() -> int:
    pid_path = spotify_session_pid_file()
    if not pid_path.exists():
        print("Spotify session is not running")
        return 0
    try:
        pid = int(pid_path.read_text().strip())
    except ValueError:
        remove_file_if_exists(pid_path)
        print("Removed invalid Spotify session pid file")
        return 0

    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        pass

    remove_file_if_exists(pid_path)
    print(f"Stopped Spotify session pid {pid}")
    return 0


def start_service() -> int:
    if not service_is_installed():
        print(f"LaunchAgent is not installed: {launch_agent_path()}")
        print("Run `uv run np install-service` first.")
        return 1

    label_ref = launchctl_label_ref()
    domain = launchctl_domain()
    if not service_is_loaded(label_ref):
        subprocess.run(["launchctl", "bootstrap", domain, str(launch_agent_path())], check=True)

    subprocess.run(["launchctl", "enable", label_ref], check=True)
    subprocess.run(["launchctl", "kickstart", "-k", label_ref], check=True)
    print(f"Started {launch_agent_label()} at {service_http_url()}")
    return 0


def stop_service() -> int:
    label_ref = launchctl_label_ref()
    domain = launchctl_domain()
    if service_is_loaded(label_ref):
        subprocess.run(["launchctl", "bootout", label_ref], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["launchctl", "bootout", domain, str(launch_agent_path())], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Stopped {launch_agent_label()}")
        return 0

    if service_is_installed():
        print(f"{launch_agent_label()} is not running")
        return 0

    print(f"LaunchAgent is not installed: {launch_agent_path()}")
    return 1


def restart_service() -> int:
    if not service_is_installed():
        print(f"LaunchAgent is not installed: {launch_agent_path()}")
        print("Run `uv run np install-service` first.")
        return 1

    stop_service()
    return start_service()


def service_status() -> int:
    label_ref = launchctl_label_ref()
    installed = service_is_installed()
    loaded = service_is_loaded(label_ref)
    pid = service_pid(label_ref) if loaded else None

    payload = {
        "label": launch_agent_label(),
        "installed": installed,
        "loaded": loaded,
        "running": pid is not None,
        "pid": pid,
        "plist_path": str(launch_agent_path()),
        "log_path": str(logs_dir() / "launchd.log"),
        "url": service_http_url(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if installed else 1


def tail_service_log(lines: int, follow: bool) -> int:
    log_path = logs_dir() / "launchd.log"
    if not log_path.exists():
        print(f"Log file does not exist yet: {log_path}")
        return 1

    content = log_path.read_text().splitlines()
    tail_lines = content[-max(lines, 0):] if lines else content
    if tail_lines:
        print("\n".join(tail_lines))

    if not follow:
        return 0

    with log_path.open("r") as handle:
        handle.seek(0, os.SEEK_END)
        try:
            while True:
                line = handle.readline()
                if line:
                    print(line, end="")
                else:
                    time.sleep(0.5)
        except KeyboardInterrupt:
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

    domain = launchctl_domain()
    label_ref = launchctl_label_ref()
    subprocess.run(["launchctl", "bootout", label_ref], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["launchctl", "bootout", domain, str(launch_agent_path())], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        subprocess.run(["launchctl", "bootstrap", domain, str(launch_agent_path())], check=True)
    except subprocess.CalledProcessError:
        # launchctl can intermittently return exit 5 even when the agent is effectively loaded.
        # If the service is not present after that failure, retry once against the fresh plist.
        if not service_is_loaded(label_ref):
            time.sleep(0.2)
            subprocess.run(["launchctl", "bootstrap", domain, str(launch_agent_path())], check=True)

    subprocess.run(["launchctl", "enable", label_ref], check=True)
    subprocess.run(["launchctl", "kickstart", "-k", label_ref], check=True)

    print(f"Installed {launch_agent_label()} and started {service_http_url()}")
    return 0


def uninstall_service() -> int:
    domain = launchctl_domain()
    label_ref = launchctl_label_ref()
    subprocess.run(["launchctl", "bootout", label_ref], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["launchctl", "bootout", domain, str(launch_agent_path())], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    output_format = getattr(args, "format", "json")

    if command == "current":
        track, providers = select_track_with_diagnostics(source)
        if output_format == "text":
            print(track.to_text(idle_text))
        else:
            payload = asdict(track)
            payload["providers"] = providers
            print(json.dumps(payload, indent=2, sort_keys=True))
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

    if command == "start-spotify-session":
        return start_spotify_session(args.interval_seconds, args.terminal)

    if command == "spotify-session-serve":
        return run_spotify_session(args.interval_seconds, idle_text)

    if command == "stop-spotify-session":
        return stop_spotify_session()

    if command == "init-config":
        return init_config()

    if command == "install-service":
        return install_service()

    if command == "start-service":
        return start_service()

    if command == "stop-service":
        return stop_service()

    if command == "restart-service":
        return restart_service()

    if command == "status":
        return service_status()

    if command == "tail":
        return tail_service_log(args.lines, args.follow)

    if command == "uninstall-service":
        return uninstall_service()

    parser.print_help()
    return 1


def cli() -> int:
    return main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(cli())

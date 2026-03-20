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
    if not track_changed and previous.get("updated_at"):
        payload["updated_at"] = previous["updated_at"]

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
            self.respond_html(self.render_dashboard())
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
            self.respond_json({"artwork_path": payload.get("artwork_path", "")})
            return

        if parsed.path == "/current_artwork.png":
            self.respond_artwork()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, fmt: str, *args) -> None:
        LOGGER.debug("HTTP %s - %s", self.address_string(), fmt % args)

    def render_dashboard(self) -> str:
        return """<!doctype html>
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
          <div class="footer-note">Live local feed for stream overlays, OBS, and operator checks.</div>
        </section>
      </div>
    </main>
  </div>
  <script>
    const titleEl = document.getElementById("title");
    const metaEl = document.getElementById("meta");
    const statusEl = document.getElementById("status");
    const sourceEl = document.getElementById("source");
    const updatedAtEl = document.getElementById("updated-at");
    const artworkImageEl = document.getElementById("artwork-image");
    const artworkEmptyEl = document.getElementById("artwork-empty");
    let lastArtworkVersion = "";

    function render(payload) {
      sourceEl.textContent = payload.source || "unknown";
      updatedAtEl.textContent = payload.updated_at || "never";
      statusEl.textContent = payload.state || "unknown";
      statusEl.className = "status state-" + (payload.state || "unknown");

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
          artworkImageEl.src = "/current_artwork.png?v=" + encodeURIComponent(version);
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

    const events = new EventSource("/events");
    events.addEventListener("now_playing", (event) => {
      render(JSON.parse(event.data));
    });
    events.onerror = () => {
      statusEl.textContent = "disconnected";
    };
  </script>
</body>
</html>"""

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

    def respond_artwork(self) -> None:
        path = current_artwork_file()
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


def service_is_loaded(label_ref: str) -> bool:
    result = subprocess.run(
        ["launchctl", "print", label_ref],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


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

    host = os.environ.get("NOW_PLAYING_HOST", "127.0.0.1")
    port = os.environ.get("NOW_PLAYING_PORT", "8976")
    print(f"Installed {launch_agent_label()} and started http://{host}:{port}/current")
    return 0


def uninstall_service() -> int:
    domain = f"gui/{os.getuid()}"
    label_ref = f"{domain}/{launch_agent_label()}"
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
        track = select_track(source)
        if output_format == "text":
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

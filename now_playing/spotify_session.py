"""Spotify terminal session management."""

import json
import os
import shlex
import time
from pathlib import Path

from now_playing.fs import remove_file_if_exists
from now_playing.logging_config import LOGGER
from now_playing.paths import repo_dir, spotify_session_pid_file
from now_playing.providers.spotify import run_osascript
from now_playing.launchd_service import service_http_url
from now_playing.sync_service import sync


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

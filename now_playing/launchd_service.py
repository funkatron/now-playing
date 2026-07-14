"""macOS LaunchAgent service management."""

import json
import os
import plistlib
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from now_playing.paths import config_env_example_file, config_env_file
from now_playing.logging_config import LOGGER
from now_playing.obs_integration import obs_enabled
from now_playing.paths import (
    current_artwork_file,
    current_song_file,
    current_track_json_file,
    data_dir,
    logs_dir,
    repo_dir,
)


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


def obs_integration_info() -> dict:
    websocket_enabled = obs_enabled()
    websocket_port = int(os.environ.get("OBSWS_PORT", "4455"))

    return {
        "browser_overlay_url": f"{service_http_url()}overlay",
        "spotify_overlay_url": f"{service_http_url()}spotify/overlay",
        "files": {
            "song": str(current_song_file()),
            "artwork": str(current_artwork_file()),
            "track_json": str(current_track_json_file()),
        },
        "websocket": {
            "enabled": websocket_enabled,
            "host": os.environ.get("OBSWS_HOST", "localhost"),
            "port": websocket_port,
            "image_input_name": os.environ.get("OBSWS_IMAGE_INPUT_NAME", "NPImage"),
            "text_input_name": os.environ.get("OBSWS_TEXT_INPUT_NAME", ""),
            "text_field": os.environ.get("OBSWS_TEXT_FIELD", "text"),
        },
    }
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


def _process_memory_mb(pid: Optional[int]) -> Optional[float]:
    if not pid:
        return None
    try:
        result = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            check=True,
            capture_output=True,
            text=True,
        )
        rss_kb = int(result.stdout.strip().split()[0])
        return round(rss_kb / 1024.0, 1)
    except Exception:
        return None


def _runtime_health() -> dict:
    url = service_http_url().rstrip("/") + "/health"
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=1.5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}


def service_status() -> int:
    label_ref = launchctl_label_ref()
    installed = service_is_installed()
    loaded = service_is_loaded(label_ref)
    pid = service_pid(label_ref) if loaded else None
    health = _runtime_health() if pid else {}

    payload = {
        "label": launch_agent_label(),
        "installed": installed,
        "loaded": loaded,
        "running": pid is not None,
        "pid": pid,
        "plist_path": str(launch_agent_path()),
        "log_path": str(logs_dir() / "launchd.log"),
        "url": service_http_url(),
        "obs": obs_integration_info(),
        "runtime": {
            "rss_mb": _process_memory_mb(pid),
            "event_clients": health.get("event_clients"),
            "threads": health.get("threads"),
        },
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

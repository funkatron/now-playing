#!/usr/bin/env python3
"""One-shot mechanical split of np_service.py into now_playing/* modules."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "np_service.py"
PKG = ROOT / "now_playing"


def lines(start: int, end: int) -> str:
    """Extract 1-indexed inclusive line range from source."""
    all_lines = SOURCE.read_text().splitlines(keepends=True)
    return "".join(all_lines[start - 1 : end])


def write(relative: str, header: str, body: str) -> None:
    path = PKG / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body)


def main() -> None:
    write(
        "logging_config.py",
        '''"""Logging and module-level defaults."""

import logging
import os

LOGGER = logging.getLogger("now_playing")

PLAYING_STATE_CODE = 1800426320
DEFAULT_SOURCE = os.environ.get("NOW_PLAYING_SOURCE", "auto")
DEFAULT_IDLE_TEXT = os.environ.get("NOW_PLAYING_IDLE_TEXT", "")


''',
        lines(86, 89),
    )

    write(
        "util.py",
        '''"""Small shared helpers."""

import re
from datetime import datetime, timezone

from now_playing.logging_config import PLAYING_STATE_CODE


''',
        lines(92, 94) + lines(268, 279),
    )

    write(
        "models.py",
        '''"""Domain models."""

from dataclasses import dataclass
from typing import Optional

from now_playing.logging_config import DEFAULT_IDLE_TEXT


''',
        lines(34, 84),
    )

    write(
        "paths.py",
        '''"""Repository and data path helpers."""

from pathlib import Path


''',
        lines(96, 229),
    )

    write(
        "fs.py",
        '''"""Atomic file writes and copies."""

import json
import shutil
from pathlib import Path


''',
        lines(232, 265),
    )

    write(
        "templates.py",
        '''"""HTML template loading."""

import os
from importlib import resources
from pathlib import Path
from typing import Optional

from now_playing.logging_config import LOGGER


''',
        lines(120, 175),
    )

    write(
        "config_env.py",
        '''"""Load config.env into os.environ."""

import os

from now_playing.paths import config_env_file


''',
        lines(282, 294),
    )

    write(
        "state.py",
        '''"""Sync state persistence."""

import json

from now_playing.fs import write_json_if_changed
from now_playing.logging_config import LOGGER
from now_playing.paths import namespaced_state_file


''',
        lines(296, 309),
    )

    write(
        "providers/apple.py",
        '''"""Apple Music provider."""

import subprocess
from pathlib import Path

from now_playing.logging_config import LOGGER, PLAYING_STATE_CODE
from now_playing.models import TrackInfo
from now_playing.util import iso_now, safe_filename


''',
        lines(312, 350) + "\n\n" + lines(427, 451),
    )

    write(
        "providers/spotify.py",
        '''"""Spotify provider via AppleScript."""

import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from now_playing.logging_config import LOGGER
from now_playing.models import TrackInfo
from now_playing.util import iso_now, safe_filename


''',
        lines(352, 479),
    )

    write(
        "providers/auto.py",
        '''"""Provider selection and diagnostics."""

from typing import Optional

from now_playing.logging_config import LOGGER
from now_playing.models import ProviderError, ProviderSnapshot, TrackInfo
from now_playing.providers.apple import get_apple_music_track
from now_playing.providers.spotify import get_spotify_track
from now_playing.util import iso_now


''',
        lines(482, 558),
    )

    write(
        "providers/__init__.py",
        '''"""Track source providers."""

from now_playing.providers.apple import extract_apple_music_artwork, get_apple_music_track
from now_playing.providers.auto import (
    inspect_provider,
    provider_snapshot,
    select_track,
    select_track_with_diagnostics,
)
from now_playing.providers.spotify import (
    fetch_spotify_artwork,
    get_spotify_track,
    query_spotify_snapshot,
    run_osascript,
    spotify_artwork_cache_path,
    spotify_query_script,
    spotify_state,
    spotify_track_fields,
)

__all__ = [
    "extract_apple_music_artwork",
    "fetch_spotify_artwork",
    "get_apple_music_track",
    "get_spotify_track",
    "inspect_provider",
    "provider_snapshot",
    "query_spotify_snapshot",
    "run_osascript",
    "select_track",
    "select_track_with_diagnostics",
    "spotify_artwork_cache_path",
    "spotify_query_script",
    "spotify_state",
    "spotify_track_fields",
]
''',
        "",
    )

    write(
        "obs_integration.py",
        '''"""OBS WebSocket integration."""

import os

from now_playing.logging_config import LOGGER
from now_playing.models import TrackInfo
from now_playing.paths import current_artwork_file


''',
        lines(561, 601),
    )

    write(
        "sync_service.py",
        '''"""Sync pipeline: providers -> files -> OBS."""

import json
from dataclasses import asdict
from pathlib import Path

from now_playing.fs import (
    copy_file_if_changed,
    remove_file_if_exists,
    write_json_if_changed,
    write_text_if_changed,
)
from now_playing.logging_config import DEFAULT_SOURCE, LOGGER
from now_playing.models import TrackInfo
from now_playing.obs_integration import update_obs
from now_playing.paths import namespaced_artwork_manifest_file, namespaced_current_artwork_file, namespaced_current_song_file, namespaced_current_track_json_file
from now_playing.providers.auto import select_track_with_diagnostics
from now_playing.state import read_previous_state, save_state
from now_playing.util import iso_now


''',
        lines(604, 709),
    )

    # Extract render methods from RequestHandler into dashboard_html.py
    handler_body = lines(746, 1797)
    dashboard_funcs = ""
    for method_name in ("render_dashboard", "render_overlay"):
        pattern = rf"    def {method_name}\(self.*?(?=    def |\Z)"
        match = re.search(pattern, handler_body, re.DOTALL)
        if not match:
            raise SystemExit(f"Could not find {method_name}")
        method_src = match.group(0)
        # Convert instance method to module function (drop self param usage is only load_html_template)
        func_src = method_src.replace(f"    def {method_name}(self, ", f"def {method_name}(")
        func_src = func_src.replace("    @staticmethod\n    def overlay_preset", "def _overlay_preset_unused")
        dashboard_funcs += func_src + "\n\n"

    write(
        "dashboard_html.py",
        '''"""Dashboard and overlay HTML rendering."""

import os
import urllib.parse

from now_playing.templates import load_html_template


''',
        dashboard_funcs,
    )

    # RequestHandler without render methods - patch do_GET to use dashboard_html
    handler_without_render = re.sub(
        r"    def render_dashboard\(self.*?(?=    def respond_json)",
        "",
        handler_body,
        count=1,
        flags=re.DOTALL,
    )

    write(
        "http_server.py",
        '''"""Stdlib HTTP server for the now-playing API."""

import json
import os
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from now_playing.dashboard_html import render_dashboard, render_overlay
from now_playing.logging_config import LOGGER
from now_playing.paths import namespaced_current_artwork_file
from now_playing.sync_service import read_current_payload, sync


''',
        lines(712, 745)
        + handler_without_render
        + lines(1736, 1797)
        + lines(1799, 1841),
    )

    # Fix RequestHandler to call module-level render functions
    http_path = PKG / "http_server.py"
    http_text = http_path.read_text()
    http_text = http_text.replace(
        'self.render_dashboard("/", True)',
        'render_dashboard("/", True)',
    )
    http_text = http_text.replace(
        'self.render_overlay("/", True, self.overlay_options(parsed.query))',
        'render_overlay("/", True, self.overlay_options(parsed.query))',
    )
    http_text = http_text.replace(
        'self.render_dashboard("/spotify", False)',
        'render_dashboard("/spotify", False)',
    )
    http_text = http_text.replace(
        'self.render_overlay("/spotify", False, self.overlay_options(parsed.query))',
        'render_overlay("/spotify", False, self.overlay_options(parsed.query))',
    )
    http_path.write_text(http_text)

    write(
        "launchd_service.py",
        '''"""macOS LaunchAgent service management."""

import json
import os
import plistlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

from now_playing.config_env import config_env_example_file, config_env_file
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


''',
        lines(1911, 2021) + lines(2144, 2283),
    )

    # Fix wrong import in launchd - config_env_file is from paths not config_env
    launchd_path = PKG / "launchd_service.py"
    launchd_text = launchd_path.read_text()
    launchd_text = launchd_text.replace(
        "from now_playing.config_env import config_env_example_file, config_env_file\n",
        "from now_playing.paths import config_env_example_file, config_env_file\n",
    )
    launchd_path.write_text(launchd_text)

    write(
        "spotify_session.py",
        '''"""Spotify terminal session management."""

import json
import os
import shlex
import time
from pathlib import Path

from now_playing.fs import remove_file_if_exists
from now_playing.logging_config import LOGGER
from now_playing.paths import repo_dir, spotify_session_pid_file
from now_playing.providers.spotify import run_osascript
from now_playing.sync_service import sync


''',
        lines(2024, 2141),
    )

    # launchd obs_integration_info and init_config - need to add init_config to launchd
    # init_config was lines 1938-1946 - already in launchd range 1911-2283? 
    # 1911 is launch_agent_label, 1938 is init_config - yes included

    # service_http_url used by spotify_session - it's in launchd_service
    # spotify_session imports service_http_url from launchd - add import fix

    spotify_path = PKG / "spotify_session.py"
    spotify_text = spotify_path.read_text()
    spotify_text = spotify_text.replace(
        "from now_playing.sync_service import sync\n\n\n",
        "from now_playing.launchd_service import service_http_url\nfrom now_playing.sync_service import sync\n\n\n",
    )
    spotify_path.write_text(spotify_text)

    write(
        "cli.py",
        '''"""CLI entrypoint for np."""

import argparse
import json
import os
import sys
from dataclasses import asdict

from now_playing.config_env import load_config_env
from now_playing.launchd_service import (
    init_config,
    install_service,
    restart_service,
    service_status,
    start_service,
    stop_service,
    tail_service_log,
    uninstall_service,
)
from now_playing.logging_config import DEFAULT_IDLE_TEXT, DEFAULT_SOURCE, LOGGER, configure_logging
from now_playing.paths import logs_dir
from now_playing.providers.auto import select_track, select_track_with_diagnostics
from now_playing.spotify_session import (
    run_spotify_session,
    start_spotify_session,
    stop_spotify_session,
)
from now_playing.sync_service import sync
from now_playing.http_server import run_server


''',
        lines(1844, 1908) + lines(2286, 2370),
    )

    # np_service.py re-exports
    reexport = '''#!/usr/bin/env python3
"""Backward-compatible facade; implementation lives in now_playing/."""

import os
import subprocess
import sys
import time
from pathlib import Path

from now_playing.cli import build_parser, cli, current_settings, main
from now_playing.config_env import load_config_env
from now_playing.dashboard_html import render_dashboard, render_overlay
from now_playing.fs import (
    copy_file_if_changed,
    remove_file_if_exists,
    write_json_if_changed,
    write_text_if_changed,
)
from now_playing.http_server import NowPlayingHTTPServer, RequestHandler, run_server
from now_playing.launchd_service import (
    env_subset,
    init_config,
    install_service,
    launch_agent_label,
    launch_agent_path,
    launchctl_domain,
    launchctl_label_ref,
    launchctl_print_lines,
    obs_integration_info,
    restart_service,
    service_http_url,
    service_is_installed,
    service_is_loaded,
    service_pid,
    service_status,
    start_service,
    stop_service,
    tail_service_log,
    uninstall_service,
)
from now_playing.logging_config import (
    DEFAULT_IDLE_TEXT,
    DEFAULT_SOURCE,
    LOGGER,
    PLAYING_STATE_CODE,
    configure_logging,
)
from now_playing.models import ProviderError, ProviderSnapshot, TrackInfo
from now_playing.obs_integration import obs_enabled, update_obs
from now_playing.paths import (
    artwork_manifest_file,
    config_env_example_file,
    config_env_file,
    current_artwork_file,
    current_song_file,
    current_track_json_file,
    data_dir,
    logs_dir,
    namespaced_artwork_manifest_file,
    namespaced_current_artwork_file,
    namespaced_current_song_file,
    namespaced_current_track_json_file,
    namespaced_state_file,
    repo_dir,
    spotify_session_pid_file,
    state_file,
)
from now_playing.templates import bundled_template, load_html_template, template_has_placeholders
from now_playing.providers.apple import extract_apple_music_artwork, get_apple_music_track
from now_playing.providers.auto import (
    inspect_provider,
    provider_snapshot,
    select_track,
    select_track_with_diagnostics,
)
from now_playing.providers.spotify import (
    fetch_spotify_artwork,
    get_spotify_track,
    query_spotify_snapshot,
    run_osascript,
    spotify_artwork_cache_path,
    spotify_query_script,
    spotify_state,
    spotify_track_fields,
)
from now_playing.spotify_session import (
    detect_terminal_app,
    launch_terminal_session,
    run_spotify_session,
    spotify_session_command,
    spotify_session_is_running,
    start_spotify_session,
    stop_spotify_session,
)
from now_playing.state import read_previous_state, save_state
from now_playing.sync_service import (
    empty_payload,
    materialize_outputs,
    read_current_payload,
    sync,
)
from now_playing.util import iso_now, is_playing_state, safe_filename

__all__ = [
    "DEFAULT_IDLE_TEXT",
    "DEFAULT_SOURCE",
    "LOGGER",
    "PLAYING_STATE_CODE",
    "NowPlayingHTTPServer",
    "ProviderError",
    "ProviderSnapshot",
    "RequestHandler",
    "TrackInfo",
    "build_parser",
    "bundled_template",
    "cli",
    "configure_logging",
    "copy_file_if_changed",
    "current_settings",
    "detect_terminal_app",
    "empty_payload",
    "env_subset",
    "extract_apple_music_artwork",
    "fetch_spotify_artwork",
    "get_apple_music_track",
    "get_spotify_track",
    "init_config",
    "inspect_provider",
    "install_service",
    "is_playing_state",
    "iso_now",
    "launch_agent_label",
    "launch_agent_path",
    "launch_terminal_session",
    "launchctl_domain",
    "launchctl_label_ref",
    "launchctl_print_lines",
    "load_config_env",
    "load_html_template",
    "main",
    "materialize_outputs",
    "obs_enabled",
    "obs_integration_info",
    "os",
    "provider_snapshot",
    "query_spotify_snapshot",
    "read_current_payload",
    "read_previous_state",
    "remove_file_if_exists",
    "render_dashboard",
    "render_overlay",
    "repo_dir",
    "restart_service",
    "run_osascript",
    "run_server",
    "run_spotify_session",
    "safe_filename",
    "save_state",
    "select_track",
    "select_track_with_diagnostics",
    "service_http_url",
    "service_is_installed",
    "service_is_loaded",
    "service_pid",
    "service_status",
    "spotify_artwork_cache_path",
    "spotify_query_script",
    "spotify_session_command",
    "spotify_session_is_running",
    "spotify_state",
    "spotify_track_fields",
    "start_service",
    "start_spotify_session",
    "stop_service",
    "stop_spotify_session",
    "subprocess",
    "sync",
    "sys",
    "tail_service_log",
    "template_has_placeholders",
    "time",
    "uninstall_service",
    "update_obs",
    "write_json_if_changed",
    "write_text_if_changed",
]

if __name__ == "__main__":
    sys.exit(cli())
'''
    (ROOT / "np_service.py").write_text(reexport)

    print("Split complete.")


if __name__ == "__main__":
    main()

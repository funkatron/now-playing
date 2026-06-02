#!/usr/bin/env python3
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

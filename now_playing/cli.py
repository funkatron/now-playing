"""CLI entrypoint for np."""

import argparse
import json
import os
import sys
from dataclasses import asdict


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Poll Apple Music or Spotify and expose now-playing state (files, HTTP, OBS).",
        epilog="Default with no subcommand: current track as JSON. See README.md for setup.",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "apple_music", "spotify"],
        help="music source (default: NOW_PLAYING_SOURCE or auto)",
    )
    parser.add_argument(
        "--idle-text",
        help="text when idle (default: NOW_PLAYING_IDLE_TEXT or empty)",
    )

    subparsers = parser.add_subparsers(dest="command")

    current_parser = subparsers.add_parser("current", help="Get the current track")
    current_parser.add_argument("--format", default="json", choices=["json", "text"])

    subparsers.add_parser("artwork", help="Get the current artwork path")
    subparsers.add_parser("sync", help="Sync track data to files and OBS")

    serve_parser = subparsers.add_parser("serve", help="Run the polling daemon and local HTTP API")
    serve_parser.add_argument("--host", default=os.environ.get("NOW_PLAYING_HOST", "127.0.0.1"), help="HTTP bind address")
    serve_parser.add_argument("--port", type=int, default=int(os.environ.get("NOW_PLAYING_PORT", "8976")), help="HTTP port")
    serve_parser.add_argument(
        "--interval-seconds",
        type=float,
        default=float(os.environ.get("INTERVAL_SECONDS", "5")),
        help="seconds between polls",
    )

    spotify_session_parser = subparsers.add_parser(
        "start-spotify-session",
        help="Launch a Spotify-pinned service in Terminal or iTerm (unstable)",
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
    subparsers.add_parser("stop-spotify-session", help="Stop the Spotify terminal session if it is running (unstable path)")

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
    import np_service as np

    source = args.source or os.environ.get("NOW_PLAYING_SOURCE", np.DEFAULT_SOURCE)
    idle_text = (
        args.idle_text
        if args.idle_text is not None
        else os.environ.get("NOW_PLAYING_IDLE_TEXT", np.DEFAULT_IDLE_TEXT)
    )
    return source, idle_text


def main(argv: list[str]) -> int:
    import np_service as np

    np.load_config_env()
    np.configure_logging()
    np.logs_dir()
    parser = build_parser()
    args = parser.parse_args(argv)

    command = args.command or "current"
    source, idle_text = current_settings(args)
    output_format = getattr(args, "format", "json")

    if command == "current":
        track, providers = np.select_track_with_diagnostics(source)
        if output_format == "text":
            print(track.to_text(idle_text))
        else:
            payload = asdict(track)
            payload["providers"] = providers
            print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if command == "artwork":
        track = np.select_track(source)
        if track.artwork_path:
            print(track.artwork_path)
        return 0

    if command == "sync":
        result = np.sync(source, idle_text)
        np.LOGGER.info(
            "Sync complete: source=%s state=%s changed=%s obs_updated=%s",
            result["track"]["source"],
            result["track"]["state"],
            result["changed"],
            result["obs_updated"],
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if command == "serve":
        return np.run_server(source, idle_text, args.host, args.port, args.interval_seconds)

    if command == "start-spotify-session":
        return np.start_spotify_session(args.interval_seconds, args.terminal)

    if command == "spotify-session-serve":
        return np.run_spotify_session(args.interval_seconds, idle_text)

    if command == "stop-spotify-session":
        return np.stop_spotify_session()

    if command == "init-config":
        return np.init_config()

    if command == "install-service":
        return np.install_service()

    if command == "start-service":
        return np.start_service()

    if command == "stop-service":
        return np.stop_service()

    if command == "restart-service":
        return np.restart_service()

    if command == "status":
        return np.service_status()

    if command == "tail":
        return np.tail_service_log(args.lines, args.follow)

    if command == "uninstall-service":
        return np.uninstall_service()

    parser.print_help()
    return 1


def cli() -> int:
    return main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(cli())

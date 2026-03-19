# Now Playing

This repo runs a small macOS background service that polls Apple Music or Spotify, writes flat files for OBS-friendly consumption, and exposes a local HTTP API on `127.0.0.1`.

## Outputs

- `_data/current_song.txt`
- `_data/current_track.json`
- `_data/current_artwork.png`
- `_data/now_playing_artworks.txt`
- `http://127.0.0.1:8976/`
- `http://127.0.0.1:8976/current`
- `http://127.0.0.1:8976/current.txt`
- `http://127.0.0.1:8976/artwork`
- `http://127.0.0.1:8976/current_artwork.png`
- `http://127.0.0.1:8976/events`
- `http://127.0.0.1:8976/health`

Text output format:

```text
"<song name>"
<artist name>
<album name>
<year if available>
```

If nothing is playing, the text output is empty by default. Set `NOW_PLAYING_IDLE_TEXT` if you want different idle text.

## Requirements

- macOS
- Python 3.9+
- Apple Music and/or Spotify installed
- OBS only if you want websocket-driven updates

## Install

```bash
brew install uv
uv sync
uv run np init-config
```

Then edit `config.env` if you want Spotify-only mode or OBS websocket pushes.

## Quick Start

Run a single sync:

```bash
uv run np sync
```

Run the daemon in the foreground:

```bash
uv run np serve
```

Install the background service with `launchd`:

```bash
uv run np install-service
```

Stop and remove it:

```bash
uv run np uninstall-service
```

Notes:

- Bare `uv run np` defaults to `current --format json`.
- Global flags such as `--source` and `--idle-text` go before the subcommand.
- Example: `uv run np --source apple_music current --format text`

## Local Viewer

If you want to start the service and immediately see the current text and artwork in a browser:

```bash
uv run np serve
open http://127.0.0.1:8976/
```

Or with the background service:

```bash
uv run np install-service
open http://127.0.0.1:8976/
```

The viewer is intentionally simple. It subscribes to `/events` with server-sent events, so text and artwork updates are pushed from the backend when the state changes instead of the browser polling `/current` on a timer.

## Smoke Test

Run the local install smoke test:

```bash
python3 scripts/smoke_install.py
```

Also verify the `launchd` service and HTTP API:

```bash
python3 scripts/smoke_install.py --with-service
```

## API

Current state as JSON:

```bash
curl http://127.0.0.1:8976/current
```

Current state as text:

```bash
curl http://127.0.0.1:8976/current.txt
```

Artwork path:

```bash
curl http://127.0.0.1:8976/artwork
```

Health:

```bash
curl http://127.0.0.1:8976/health
```

Current artwork file:

```bash
curl -I http://127.0.0.1:8976/current_artwork.png
```

Browser viewer:

```bash
open http://127.0.0.1:8976/
```

## OBS

The safest OBS setup is file-based:

1. Point a text source at `_data/current_song.txt`.
2. Point an image source at `_data/current_artwork.png`.

That keeps OBS simple and avoids reconnect churn.

If you also want websocket pushes, edit `config.env`:

```bash
OBSWS_ENABLED=1
OBSWS_HOST=localhost
OBSWS_PORT=4455
OBSWS_PASSWORD=your-password
OBSWS_IMAGE_INPUT_NAME=NPImage
OBSWS_TEXT_INPUT_NAME=NPText
OBSWS_TEXT_FIELD=text
```

With websocket mode enabled, the service will push image updates and optionally text updates when state changes.

## Configuration

Available environment variables:

- `NOW_PLAYING_SOURCE=auto|apple_music|spotify`
  Chooses which provider to read. `auto` prefers Apple Music when it is actively playing, otherwise Spotify.
- `NOW_PLAYING_IDLE_TEXT=...`
  Text written to `_data/current_song.txt` when nothing is playing. Leave blank for an empty file.
- `NOW_PLAYING_HOST=127.0.0.1`
  Host interface for the local HTTP API. Keep this on loopback unless you intentionally want remote access.
- `NOW_PLAYING_PORT=8976`
  Port for the local HTTP API.
- `INTERVAL_SECONDS=5`
  Polling interval used by the daemon in `serve` mode and the installed `launchd` service.
- `PYTHON_LOG_LEVEL=INFO`
  Logging level for the CLI and daemon. Useful values are `DEBUG`, `INFO`, `WARNING`, and `ERROR`.
- `OBSWS_ENABLED=1`
  Enables OBS websocket pushes. Leave this as `0` if OBS is only reading the flat files directly.
- `OBSWS_HOST=localhost`
  OBS websocket host.
- `OBSWS_PORT=4455`
  OBS websocket port.
- `OBSWS_PASSWORD=...`
  OBS websocket password.
- `OBSWS_IMAGE_INPUT_NAME=NPImage`
  OBS image input to update with `_data/current_artwork.png`.
- `OBSWS_TEXT_INPUT_NAME=NPText`
  Optional OBS text input to update with the rendered now-playing text. Leave blank if OBS reads `_data/current_song.txt` itself.
- `OBSWS_TEXT_FIELD=text`
  Field name used for the selected OBS text input.
- `NOW_PLAYING_LAUNCHD_LABEL=com.funkatron.now-playing`
  Per-user launchd label written into `~/Library/LaunchAgents/`.

The easiest way to manage those is in `config.env`, which the Python CLI loads automatically.

## Commands

Global flags:

```bash
uv run np [--source auto|apple_music|spotify] [--idle-text "Idle text"] <command>
```

Command reference:

```bash
uv run np current --format json
uv run np current --format text
uv run np artwork
uv run np sync
uv run np serve
uv run np install-service
uv run np uninstall-service
```

- `current --format json`
  Prints the normalized current-state payload. This is the best command for debugging provider detection.
- `current --format text`
  Prints the four-line rendered text view that mirrors `_data/current_song.txt`.
- `artwork`
  Prints the current artwork path if one exists.
- `sync`
  Runs one polling pass, updates the flat files under `_data/`, and performs OBS updates if enabled.
- `serve`
  Runs the in-process polling loop and local HTTP API in the foreground.
- `init-config`
  Creates `config.env` from `config.env.example` if it does not already exist.
- `install-service`
  Writes the per-user LaunchAgent plist, reloads the service, and leaves it running in the background.
- `uninstall-service`
  Stops the per-user LaunchAgent and removes the installed plist.

Useful examples:

```bash
uv run np
uv run np --source apple_music current --format text
uv run np --source spotify sync
uv run np serve --host 127.0.0.1 --port 8976 --interval-seconds 2
uv run np install-service
curl http://127.0.0.1:8976/current
```

# Now Playing

This repo runs a small macOS now-playing service. It polls Apple Music or Spotify, keeps local outputs up to date, and exposes the current state over HTTP on `127.0.0.1`.

Out of the box, it provides:

- **flat-file output** that works well with OBS and other local consumers
- optional **OBS websocket push** for text and artwork updates
- a **local HTTP API** plus a simple **browser viewer**
- support for both **Apple Music** and **Spotify**, with **auto-detection** of the active provider

## Start Here

Install dependencies and create a local config file:

```bash
brew install uv
uv sync
uv run np init-config
```

Run the service in the foreground and open the local viewer:

```bash
uv run np serve
open http://127.0.0.1:8976/
```

Install the per-user background service:

```bash
uv run np install-service
uv run np status
open http://127.0.0.1:8976/
```

Notes:

- Bare `uv run np` defaults to `current --format json`.
- Global flags such as `--source` and `--idle-text` go before the subcommand.
- Example: `uv run np --source apple_music current --format text`
- `install-service` leaves the background service installed and running until you explicitly stop or remove it.
- `uninstall-service` stops the background service and removes the installed LaunchAgent plist from `~/Library/LaunchAgents/`.

The service reads [`config.env`](/Users/coj/src/now-playing/config.env) automatically if it exists. Start with [`config.env.example`](/Users/coj/src/now-playing/config.env.example) and only change what you actually need.

## Outputs And Endpoints

The service writes the following files to `_data/`:

- `_data/current_song.txt`
- `_data/current_track.json`
- `_data/current_artwork.png`
- `_data/now_playing_artworks.txt`

The HTTP API provides the following endpoints:

- `GET /current` - current state as JSON
- `GET /current.txt` - current state as text (4-line rendered view)
- `GET /artwork` - current artwork path as JSON, or `null` if there is no artwork
- `GET /current_artwork.png` - current artwork file
- `GET /events` - server-sent events stream for live updates
- `GET /health` - health check
- `GET /` - browser viewer

## Requirements

- macOS
- Python 3.9+
- Apple Music and/or Spotify installed
- OBS only if you want websocket-driven updates

## Foreground And Background

Run one sync pass:

```bash
uv run np sync
```

Run the service in the foreground:

```bash
uv run np serve
```

Manage the installed background service:

```bash
uv run np install-service
uv run np start-service
uv run np stop-service
uv run np restart-service
uv run np status
uv run np tail
uv run np tail --follow
uv run np uninstall-service
```

The browser viewer is intentionally simple. It subscribes to `/events` with server-sent events, so text and artwork updates are pushed from the backend instead of the page polling `/current` on a timer.

Debugging notes:
- If `uv run np serve` reports `Address already in use`, stop the installed service first with `uv run np stop-service` or `uv run np uninstall-service`, or run the foreground server on a different port.
- If provider detection looks wrong, the foreground viewer is the easiest way to debug it:

```bash
uv run np stop-service
uv run np serve
open http://127.0.0.1:8976/
```

That keeps the service attached to your terminal so Python exceptions and provider issues are visible immediately.

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

`/current` is the machine-facing JSON endpoint. `/` is the human-facing viewer.

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

The easiest way to manage these is in `config.env`, which the Python CLI loads automatically.

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
uv run np start-service
uv run np stop-service
uv run np restart-service
uv run np status
uv run np tail
uv run np tail --follow
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
- `start-service`
  Starts the installed LaunchAgent without rewriting the plist.
- `stop-service`
  Stops the installed LaunchAgent without removing the plist from `~/Library/LaunchAgents/`.
- `restart-service`
  Stops and starts the installed LaunchAgent in place.
- `status`
  Prints JSON describing whether the LaunchAgent is installed, loaded, and currently running, plus the plist path, log path, and local viewer URL.
- `tail`
  Prints the recent `launchd` log output. Use `--follow` to stream it until you press `Ctrl-C`.
- `uninstall-service`
  Stops the per-user LaunchAgent and removes the installed plist.

Useful examples:

```bash
uv run np
uv run np --source apple_music current --format text
uv run np --source spotify sync
uv run np serve --host 127.0.0.1 --port 8976 --interval-seconds 2
uv run np install-service
uv run np status
uv run np tail --follow
uv run np restart-service
curl http://127.0.0.1:8976/current
```

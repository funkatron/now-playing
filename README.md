# Now Playing

This repo runs a small macOS background service that polls Apple Music or Spotify, writes flat files for OBS-friendly consumption, and exposes a local HTTP API on `127.0.0.1`.

## Outputs

- `_data/current_song.txt`
- `_data/current_track.json`
- `_data/current_artwork.png`
- `_data/now_playing_artworks.txt`
- `http://127.0.0.1:8976/current`
- `http://127.0.0.1:8976/current.txt`
- `http://127.0.0.1:8976/artwork`
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
- `NOW_PLAYING_IDLE_TEXT=...`
- `NOW_PLAYING_HOST=127.0.0.1`
- `NOW_PLAYING_PORT=8976`
- `INTERVAL_SECONDS=5`
- `PYTHON_BIN=/absolute/path/to/python`
- `PYTHON_LOG_LEVEL=INFO`
- `OBSWS_ENABLED=1`
- `OBSWS_HOST=localhost`
- `OBSWS_PORT=4455`
- `OBSWS_PASSWORD=...`
- `OBSWS_IMAGE_INPUT_NAME=NPImage`
- `OBSWS_TEXT_INPUT_NAME=NPText`
- `OBSWS_TEXT_FIELD=text`
- `NOW_PLAYING_LAUNCHD_LABEL=com.funkatron.now-playing`

The easiest way to manage those is in `config.env`, which the Python CLI loads automatically.

## Commands

```bash
uv run np current --format json
uv run np current --format text
uv run np artwork
uv run np sync
uv run np serve
uv run np install-service
uv run np uninstall-service
```

# Now Playing

This repo runs a small macOS **now-playing** service. It polls Apple Music or Spotify, keeps local outputs up to date, and exposes current state over HTTP on `127.0.0.1`.

**What you get:**

- **Flat-file output** for OBS and other local consumers
- Optional **OBS WebSocket** push for text and artwork
- A **local HTTP API** and a simple **browser viewer**
- **Apple Music** and **Spotify**, with **auto-detection** of the active provider

## Contents

- [Requirements](#requirements)
- [Start here](#start-here)
- [Outputs and HTTP endpoints](#outputs-and-http-endpoints)
- [Foreground and background](#foreground-and-background)
- [Smoke test](#smoke-test)
- [API examples (curl)](#api-examples-curl)
- [OBS](#obs)
- [Configuration](#configuration)
- [Commands](#commands)
- [Docs maintenance](#docs-maintenance)

## Requirements

- macOS
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (`brew install uv`)
- Apple Music and/or Spotify installed
- OBS only if you want WebSocket-driven updates (flat files work without it)

## Start here

Install dependencies and create a local config file:

```bash
brew install uv
uv sync
uv run np init-config
```

Run the service in the foreground and open the viewer:

```bash
uv run np serve
open http://127.0.0.1:8976/
```

Or install the per-user background service:

```bash
uv run np install-service
uv run np status
open http://127.0.0.1:8976/
```

**Behavior notes**

- A bare `uv run np` runs `current --format json`.
- Global flags such as `--source` and `--idle-text` go **before** the subcommand, e.g. `uv run np --source apple_music current --format text`.
- `install-service` leaves the LaunchAgent installed and running until you stop or remove it.
- `uninstall-service` stops the service and removes the plist from `~/Library/LaunchAgents/`.
- **Apple Music** fits the background LaunchAgent path best.
- **Spotify** is easier to rely on from an interactive terminal session than from the background agent (see [Foreground and background](#foreground-and-background)).

The service loads [`config.env`](config.env) when present. Copy from [`config.env.example`](config.env.example) and change only what you need.

## Outputs and HTTP endpoints

### Files (`_data/`)

| File | Role |
| --- | --- |
| `_data/current_song.txt` | Rendered text for OBS or editors |
| `_data/current_track.json` | Structured track payload |
| `_data/current_artwork.png` | Current artwork image |
| `_data/now_playing_artworks.txt` | Newline-separated list of artwork paths (when the service tracks multiple) |

### HTTP routes

**Core**

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/current` | Current state as JSON |
| `GET` | `/current.txt` | Current state as plain text (four-line view) |
| `GET` | `/artwork` | Artwork path as JSON, or `null` if none |
| `GET` | `/current_artwork.png` | Current artwork binary |
| `GET` | `/events` | Server-Sent Events stream for live UI updates |
| `GET` | `/health` | Health check |
| `GET` | `/` | Browser viewer |

**Spotify interactive worker** (requires `start-spotify-session`; see below)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/spotify/current` | Spotify-only state as JSON |
| `GET` | `/spotify/current.txt` | Spotify-only text view |
| `GET` | `/spotify/artwork` | Spotify-only artwork path as JSON |
| `GET` | `/spotify/current_artwork.png` | Spotify-only artwork file |
| `GET` | `/spotify/` | Spotify-only viewer |

## Foreground and background

**One-shot sync** (writes `_data/` once):

```bash
uv run np sync
```

**Foreground server** (polling + HTTP in your terminal):

```bash
uv run np serve
```

**Background service** (LaunchAgent):

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

### Spotify interactive session

If you need Spotify outside the normal LaunchAgent flow:

```bash
uv run np start-spotify-session
uv run np stop-spotify-session
```

This starts a separate Spotify polling worker in Terminal or iTerm (not via `launchd`). The main process still serves `/` and the usual API; the extra Spotify routes and viewer live under `/spotify/`.

| Action | What to run |
| --- | --- |
| Check that it works | `open http://127.0.0.1:8976/spotify/` or `curl http://127.0.0.1:8976/spotify/current` |
| Stop the worker | `uv run np stop-spotify-session` (does not stop `np serve` in another terminal) |

### Viewer

The browser UI is minimal: it uses **Server-Sent Events** on `/events`, so updates push from the server instead of polling `/current` on a timer.

### Debugging

- **Port in use:** If `uv run np serve` prints `Address already in use`, stop the installed agent (`uv run np stop-service` or `uninstall-service`) or bind a different port.
- **Wrong provider:** Run in the foreground so errors print to the terminal:

```bash
uv run np stop-service
uv run np serve
open http://127.0.0.1:8976/
```

## Smoke test

```bash
python3 scripts/smoke_install.py
```

With LaunchAgent + HTTP checks:

```bash
python3 scripts/smoke_install.py --with-service
```

## API examples (curl)

Use the same paths as in [HTTP routes](#http-routes). Examples:

```bash
curl http://127.0.0.1:8976/current
curl http://127.0.0.1:8976/current.txt
curl http://127.0.0.1:8976/artwork
curl http://127.0.0.1:8976/health
curl -I http://127.0.0.1:8976/current_artwork.png
```

Viewers:

```bash
open http://127.0.0.1:8976/
open http://127.0.0.1:8976/spotify/
```

- `/current` — machine-facing JSON.
- `/` — human-facing viewer.
- `/spotify/current` and `/spotify/` — Spotify worker (when that session is running).

## OBS

**Recommended:** file-based integration.

1. Point a text source at `_data/current_song.txt`.
2. Point an image source at `_data/current_artwork.png`.

That avoids WebSocket reconnect churn.

**Optional WebSocket pushes:** set in `config.env`:

```bash
OBSWS_ENABLED=1
OBSWS_HOST=localhost
OBSWS_PORT=4455
OBSWS_PASSWORD=your-password
OBSWS_IMAGE_INPUT_NAME=NPImage
OBSWS_TEXT_INPUT_NAME=NPText
OBSWS_TEXT_FIELD=text
```

When enabled, the service pushes image updates and optional text updates on state changes.

## Configuration

Set variables in [`config.env`](config.env) (loaded automatically by the CLI). Summary:

| Variable | Purpose |
| --- | --- |
| `NOW_PLAYING_SOURCE` | `auto`, `apple_music`, or `spotify`. `auto` prefers Apple Music when it is playing, otherwise Spotify. |
| `NOW_PLAYING_IDLE_TEXT` | Text for `_data/current_song.txt` when idle; leave empty for an empty file. |
| `NOW_PLAYING_HOST` | Bind address for the HTTP API (keep `127.0.0.1` unless you need remote access). |
| `NOW_PLAYING_PORT` | HTTP port (default `8976`). |
| `INTERVAL_SECONDS` | Poll interval for `serve` and the LaunchAgent service. |
| `PYTHON_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |
| `OBSWS_ENABLED` | `1` to enable OBS WebSocket; `0` for files only. |
| `OBSWS_HOST` / `OBSWS_PORT` / `OBSWS_PASSWORD` | OBS WebSocket connection. |
| `OBSWS_IMAGE_INPUT_NAME` | OBS image input updated with artwork. |
| `OBSWS_TEXT_INPUT_NAME` | Optional text input; leave blank if OBS reads `_data/current_song.txt` directly. |
| `OBSWS_TEXT_FIELD` | Field name on the selected text input. |
| `NOW_PLAYING_LAUNCHD_LABEL` | Label for the plist under `~/Library/LaunchAgents/`. |

## Commands

Global pattern:

```bash
uv run np [--source auto|apple_music|spotify] [--idle-text "Idle text"] <command>
```

**Reference**

| Command | What it does |
| --- | --- |
| `current --format json` | Current state JSON; best for debugging provider detection. |
| `current --format text` | Four-line text (matches `_data/current_song.txt`). |
| `artwork` | Prints artwork path if present. |
| `sync` | One poll; updates `_data/` and OBS if enabled. |
| `serve` | Foreground poll loop + HTTP API. |
| `init-config` | Creates `config.env` from `config.env.example` if missing. |
| `install-service` | Writes LaunchAgent plist and starts the background service. |
| `start-service` / `stop-service` / `restart-service` | Control the installed agent without removing the plist. |
| `status` | JSON: installed, loaded, running, plist path, log path, viewer URL. |
| `tail` / `tail --follow` | Recent `launchd` logs; `--follow` streams until Ctrl-C. |
| `start-spotify-session` | Spotify worker in Terminal/iTerm when background path is unreliable. |
| `stop-spotify-session` | Stops that worker session. |
| `uninstall-service` | Stops service and removes the plist. |

**Examples**

```bash
uv run np
uv run np --source apple_music current --format text
uv run np --source spotify sync
uv run np serve --host 127.0.0.1 --port 8976 --interval-seconds 2
uv run np install-service
uv run np status
uv run np tail --follow
uv run np restart-service
uv run np start-spotify-session
curl http://127.0.0.1:8976/current
curl http://127.0.0.1:8976/spotify/current
```

## Docs maintenance

Keep the happy path before deep reference. When you add commands, routes, or side effects, update this file and the [Contents](#contents) list if you add or rename sections.

**Layout:** This README is the operator-facing guide in one place. Splitting into multiple files under `docs/` is only worth it if the README stops being easy to scroll and search—until then, prefer one file plus [TOOL_DOCS_NOTES.md](TOOL_DOCS_NOTES.md) and [AGENTS.md](AGENTS.md) for process and agent context.

# Now Playing

This repo provides a small macOS now-playing service. It polls Apple Music or Spotify, keeps local outputs up to date, and serves current state over HTTP on `127.0.0.1`.

**What you get:**

- Flat-file output for OBS and other local consumers
- Optional OBS WebSocket pushes for text and artwork
- A local HTTP API and simple browser viewer
- Apple Music and Spotify, with automatic detection of the active source

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
- Python 3.9+
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

- `uv run np` (with no subcommand) runs `current --format json`.
- Global flags such as `--source` and `--idle-text` go before the subcommand, for example: `uv run np --source apple_music current --format text`.
- `install-service` leaves the LaunchAgent installed and running until you stop or remove it.
- `uninstall-service` stops the service and removes the plist from `~/Library/LaunchAgents/`.
- Apple Music is the best fit for the background LaunchAgent path.
- Spotify is usually more reliable from an interactive terminal session than from the background agent (see [Foreground and background](#foreground-and-background)).

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

Core routes

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/current` | Current state as JSON |
| `GET` | `/current.txt` | Current state as plain text (four-line view) |
| `GET` | `/artwork` | Artwork path as JSON, or `null` if none |
| `GET` | `/current_artwork.png` | Current artwork binary |
| `GET` | `/events` | Server-Sent Events stream for live UI updates |
| `GET` | `/health` | Health check |
| `GET` | `/` | Browser viewer |
| `GET` | `/overlay` | Transparent Browser Source overlay for OBS |

Spotify interactive worker routes (requires `start-spotify-session`; see below)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/spotify/current` | Spotify-only state as JSON |
| `GET` | `/spotify/current.txt` | Spotify-only text view |
| `GET` | `/spotify/artwork` | Spotify-only artwork path as JSON |
| `GET` | `/spotify/current_artwork.png` | Spotify-only artwork file |
| `GET` | `/spotify/` | Spotify-only viewer |
| `GET` | `/spotify/overlay` | Spotify-only transparent overlay |

## Foreground and background

One-shot sync (writes `_data/` once):

```bash
uv run np sync
```

Foreground server (polling + HTTP in your terminal):

```bash
uv run np serve
```

Background service (LaunchAgent):

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

The browser UI is minimal: it uses Server-Sent Events on `/events`, so updates push from the server instead of polling `/current` on a timer.

### Debugging

- Port in use: If `uv run np serve` prints `Address already in use`, stop the installed agent (`uv run np stop-service` or `uninstall-service`) or bind a different port.
- Wrong provider: Run in the foreground so errors print to the terminal:

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
- `/overlay` — OBS Browser Source overlay.
- `/spotify/current`, `/spotify/`, and `/spotify/overlay` — Spotify worker (when that session is running).

## OBS

Use one of these three modes:

| Goal | Recommended path |
| --- | --- |
| One source with artwork + text in one widget | Browser Source (`/overlay`) |
| Most stable local setup | File sources (`current_song.txt` + `current_artwork.png`) |
| Push updates directly into named OBS inputs | WebSocket (`OBSWS_*`) |

Start with service health and integration values:

```bash
uv run np status
```

Use the `obs.files.*` absolute paths and `obs.*overlay_url` values from that JSON directly in OBS.

### Browser Source (overlay URL)

1. Start the service: `uv run np serve` (or `uv run np install-service`).
2. In OBS: **Sources → + → Browser**.
3. URL: `http://127.0.0.1:8976/overlay` (or `obs.browser_overlay_url` from `uv run np status`).
4. Set width/height to match your scene layout (for example 760x184), then position as needed.

Spotify-only worker overlay:

- URL: `http://127.0.0.1:8976/spotify/overlay`
- Start worker first: `uv run np start-spotify-session`

### Overlay customization

#### Quick recipes

Use these Browser Source URLs directly in OBS:

| Goal | URL |
| --- | --- |
| Compact default | `http://127.0.0.1:8976/overlay?preset=compact` |
| TV mode | `http://127.0.0.1:8976/overlay?preset=tv` |
| TV mode with fewer line breaks | `http://127.0.0.1:8976/overlay?preset=tv&max_lines=1` |
| TV mode, hide status line | `http://127.0.0.1:8976/overlay?preset=tv&hide_status=1` |
| TV mode, lighter panel | `http://127.0.0.1:8976/overlay?preset=tv&panel_opacity=0.50` |

Spotify worker versions use the same flags on `/spotify/overlay`, for example:
`http://127.0.0.1:8976/spotify/overlay?preset=tv&max_lines=1`.

#### URL flags reference

| URL flag | Example | Env default | Purpose |
| --- | --- | --- | --- |
| `preset` | `?preset=tv` | `NOW_PLAYING_OVERLAY_PRESET` | `compact` or `tv` layout scale. |
| `hide_status` | `?hide_status=1` | `NOW_PLAYING_OVERLAY_HIDE_STATUS` | Hide or show the PLAYING/IDLE label. |
| `max_lines` | `?max_lines=1` | `NOW_PLAYING_OVERLAY_MAX_LINES` | Clamp title + metadata labels to 1-3 lines. |
| `panel_opacity` | `?panel_opacity=0.50` | `NOW_PLAYING_OVERLAY_PANEL_OPACITY` | Overlay panel opacity (0.20-0.95). |

URL flags override env defaults when both are set.

#### Template override quickstart

1. Copy bundled templates into a local folder you control:

```bash
mkdir -p "$HOME/.config/now-playing/templates"
cp now_playing/templates/dashboard.html "$HOME/.config/now-playing/templates/dashboard.html"
cp now_playing/templates/overlay.html "$HOME/.config/now-playing/templates/overlay.html"
```

2. Edit those files and keep required placeholders intact (see below).
3. Point `config.env` at your directory:

```bash
NOW_PLAYING_TEMPLATE_DIR=/Users/<you>/.config/now-playing/templates
```

4. Restart the service:

```bash
uv run np stop-service
uv run np start-service
```

If you run in foreground instead of LaunchAgent, restart with `Ctrl+C` then `uv run np serve`.

#### Precedence (what wins)

For overlay behavior:

1. URL query flags (`/overlay?...`)
2. `config.env` / environment defaults
3. built-in defaults

This lets you keep a stable default in `config.env` and still tune per-scene URLs in OBS.

#### Template overrides

- `NOW_PLAYING_DASHBOARD_TEMPLATE_PATH` and `NOW_PLAYING_OVERLAY_TEMPLATE_PATH` can point to custom HTML files.
- `NOW_PLAYING_TEMPLATE_DIR` can point to a directory containing `dashboard.html` and `overlay.html`.
- Explicit `*_TEMPLATE_PATH` values take precedence over `NOW_PLAYING_TEMPLATE_DIR`.

Template source precedence:

1. `NOW_PLAYING_*_TEMPLATE_PATH`
2. `NOW_PLAYING_TEMPLATE_DIR`
3. bundled templates (`now_playing/templates/*.html`)
4. in-code fallback template

#### Required placeholders in custom templates

`dashboard.html` must include:

- `__ENDPOINT_PREFIX__`
- `__USE_SSE__`

`overlay.html` must include:

- `__ENDPOINT_PREFIX__`
- `__USE_SSE__`
- `__OVERLAY_PRESET__`
- `__OVERLAY_STATUS_CLASS__`
- `__OVERLAY_MAX_LINES__`
- `__OVERLAY_PANEL_OPACITY__`

If a custom template is missing required placeholders, the service logs a warning and automatically falls back to the next source in the precedence list.

### File sources (text + image)

1. Run `uv run np status` and copy `obs.files.song` and `obs.files.artwork`.
2. In OBS: **Sources → + → Text** (or **Text (GDI+)**) and enable **Read from file** with `obs.files.song`.
3. In OBS: **Sources → + → Image** and select `obs.files.artwork`.

This path avoids WebSocket reconnect churn and works even when OBS WebSocket is disabled.

### WebSocket push (optional)

Set in `config.env`:

```bash
OBSWS_ENABLED=1
OBSWS_HOST=localhost
OBSWS_PORT=4455
OBSWS_PASSWORD=your-password
OBSWS_IMAGE_INPUT_NAME=NPImage
OBSWS_TEXT_INPUT_NAME=NPText
OBSWS_TEXT_FIELD=text
```

Then:

1. In OBS, enable WebSocket server and set matching host/port/password.
2. Create input names that match `OBSWS_IMAGE_INPUT_NAME` and `OBSWS_TEXT_INPUT_NAME`.
3. Run `uv run np sync` or `uv run np serve`; updates are pushed on track/artwork change.

### Recovery checks

- **Service not reachable:** `curl http://127.0.0.1:8976/health`
- **Need current paths/URLs again:** `uv run np status`
- **Port already used:** stop existing service (`uv run np stop-service`) or run `uv run np serve --port <other-port>`

## Configuration

Set variables in [`config.env`](config.env) (loaded automatically by the CLI). Summary:

| Variable | Purpose |
| --- | --- |
| `NOW_PLAYING_SOURCE` | `auto`, `apple_music`, or `spotify`. `auto` prefers Apple Music when it is playing, otherwise Spotify. |
| `NOW_PLAYING_IDLE_TEXT` | Text for `_data/current_song.txt` when idle; leave empty for an empty file. |
| `NOW_PLAYING_HOST` | Bind address for the HTTP API (keep `127.0.0.1` unless you need remote access). |
| `NOW_PLAYING_PORT` | HTTP port (default `8976`). |
| `NOW_PLAYING_OVERLAY_PRESET` | Default overlay preset: `compact` or `tv`. |
| `NOW_PLAYING_OVERLAY_HIDE_STATUS` | `1` hides status label on overlays; `0` shows it. |
| `NOW_PLAYING_OVERLAY_MAX_LINES` | Default line clamp for title + metadata on overlays (1-3). |
| `NOW_PLAYING_OVERLAY_PANEL_OPACITY` | Default panel opacity for overlays (0.20-0.95). |
| `NOW_PLAYING_DASHBOARD_TEMPLATE_PATH` | Optional absolute path to override dashboard HTML template. |
| `NOW_PLAYING_OVERLAY_TEMPLATE_PATH` | Optional absolute path to override overlay HTML template. |
| `NOW_PLAYING_TEMPLATE_DIR` | Optional directory override containing `dashboard.html` and `overlay.html`. |
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

Reference

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
| `status` | JSON: install/runtime state plus OBS overlay URLs, file paths, and WebSocket settings. |
| `tail` / `tail --follow` | Recent `launchd` logs; `--follow` streams until Ctrl-C. |
| `start-spotify-session` | Spotify worker in Terminal/iTerm when background path is unreliable. |
| `stop-spotify-session` | Stops that worker session. |
| `uninstall-service` | Stops service and removes the plist. |

Examples

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

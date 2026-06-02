# Now Playing

macOS service that polls Apple Music or Spotify, writes local files for OBS, and serves current state over HTTP on `127.0.0.1`.

**What you get**

- Flat files under `_data/` for OBS and scripts
- Optional OBS WebSocket pushes for artwork and text
- HTTP JSON API, browser viewer, and transparent OBS overlay
- Automatic source selection (`auto`) or a fixed provider

## Contents

- [Requirements](#requirements)
- [Start here](#start-here)
- [How do I…](#how-do-i)
- [Outputs and HTTP endpoints](#outputs-and-http-endpoints)
- [Foreground and background](#foreground-and-background)
- [Smoke test](#smoke-test)
- [OBS](#obs)
- [Configuration](#configuration)
- [Commands](#commands)
- [API examples (curl)](#api-examples-curl)
- [Docs map](#docs-map)

## Requirements

- macOS
- Python 3.9+
- [uv](https://github.com/astral-sh/uv) — `brew install uv`
- Apple Music and/or Spotify installed
- OBS only if you use WebSocket push or Browser Source (flat files work without OBS running)

## Start here

If you run one command after clone, run this:

```bash
brew install uv    # skip if uv is already installed
uv sync
uv run np init-config
uv run np serve
open http://127.0.0.1:8976/
```

That starts the poll loop and HTTP API in your terminal. Press `Ctrl+C` to stop.

**Background service (optional)** — installs a LaunchAgent that keeps running after you close the terminal (until you stop or uninstall it):

```bash
uv run np install-service
uv run np status
open http://127.0.0.1:8976/
```

**Know it is working**

```bash
curl http://127.0.0.1:8976/health          # {"status":"ok"}
uv run np                                  # current track JSON on stdout
ls _data/current_track.json _data/current_song.txt
```

**Stop it**

| Mode | Stop with |
| --- | --- |
| Foreground (`serve`) | `Ctrl+C` in that terminal |
| LaunchAgent | `uv run np stop-service` |
| Remove LaunchAgent completely | `uv run np uninstall-service` |

**Behavior notes**

- `uv run np` with no subcommand runs `current --format json`.
- Put global flags before the subcommand: `uv run np --source apple_music current --format text`.
- `install-service` leaves the agent installed and running until you stop or uninstall it.
- Apple Music fits the background LaunchAgent path best. **Spotify (unstable):** prefer an interactive terminal session; the dedicated `/spotify/*` + `start-spotify-session` path is experimental (see [Foreground and background](#foreground-and-background)).
- Settings load from [`config.env`](config.env) when present (copy from [`config.env.example`](config.env.example)). See [Configuration](#configuration) for precedence.

## How do I…

| Goal | Command | Success looks like |
| --- | --- | --- |
| See current track (live, no file write) | `uv run np` | JSON on stdout; does not update `_data/` |
| Write `_data/` once | `uv run np sync` | `_data/current_*` updated |
| Run locally | `uv run np serve` | HTTP on `127.0.0.1:8976` |
| Install background service | `uv run np install-service` | `uv run np status` → `"installed": true`; `"running": true` when launchd has a PID |
| Check service + OBS paths | `uv run np status` | JSON with `url`, `obs.browser_overlay_url`, `obs.files.*` (exit `1` if plist not installed) |
| Spotify worker + HTTP **(unstable)** | `serve` or `install-service` **and** `start-spotify-session` | `spotify_*` files update; `/spotify/*` responds (may break across macOS/Spotify updates) |
| Tail background logs | `uv run np tail --follow` | Lines from `_logs/launchd.log` |
| Debug wrong provider | `uv run np stop-service` then `uv run np serve` | Errors print in the foreground terminal |
| Fix port in use | `uv run np stop-service` or `uv run np serve --port 8977` | `serve` starts without "Address already in use" |

Machine-facing JSON: `GET /current`. Human viewer: `GET /`. OBS overlay: `GET /overlay`.

## Outputs and HTTP endpoints

### Files (`_data/`)

Written by `sync` and by `serve` / the LaunchAgent on each poll.

| File | Role |
| --- | --- |
| `_data/current_song.txt` | Rendered text for OBS or editors |
| `_data/current_track.json` | Structured track payload + provider diagnostics |
| `_data/current_artwork.png` | Current artwork image |
| `_data/now_playing_artworks.txt` | Newline-separated artwork path(s) |
| `_data/sync_state.json` | Internal fingerprint of last written track (for change detection) |

Spotify terminal worker uses parallel names: `spotify_current_song.txt`, `spotify_current_track.json`, `spotify_current_artwork.png`, `spotify_now_playing_artworks.txt`, `spotify_sync_state.json`, and `spotify-session.pid`.

Artwork cache (outside the repo): `~/.now-playing/artwork-cache/`.

### HTTP routes

Default base URL: `http://127.0.0.1:8976` (override with `NOW_PLAYING_HOST` / `NOW_PLAYING_PORT`).

**Core** (live poll from the main `serve` process)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/current` | Current state as JSON |
| `GET` | `/current.txt` | Plain text (four-line view) |
| `GET` | `/artwork` | `{"artwork_path": …}` or null |
| `GET` | `/current_artwork.png` | Artwork PNG |
| `GET` | `/events` | Server-Sent Events for live UI |
| `GET` | `/health` | `{"status":"ok"}` |
| `GET` | `/` | Browser viewer |
| `GET` | `/overlay` | Transparent Browser Source overlay |

**Spotify worker (unstable)** — file-backed; requires `start-spotify-session`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/spotify/current` | Spotify namespace JSON |
| `GET` | `/spotify/current.txt` | Spotify text view |
| `GET` | `/spotify/artwork` | Spotify artwork path JSON |
| `GET` | `/spotify/current_artwork.png` | Spotify artwork PNG |
| `GET` | `/spotify/` | Spotify-only viewer |
| `GET` | `/spotify/overlay` | Spotify-only overlay |

Overlay URL flags (`preset`, `hide_status`, `max_lines`, `panel_opacity`) are documented under [OBS → Overlay customization](#overlay-customization).

## Foreground and background

**One-shot sync** (writes `_data/` once, no HTTP server):

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
uv run np start-service      # if already installed but stopped
uv run np stop-service
uv run np restart-service
uv run np status
uv run np tail
uv run np tail --follow
uv run np uninstall-service
```

### Spotify interactive session (unstable)

This path is **unstable**: separate Terminal/iTerm worker, `spotify_*` files, and `/spotify/*` HTTP routes. Prefer Apple Music + LaunchAgent for production streams until Spotify support stabilizes.

When the LaunchAgent path is unreliable for Spotify (expected today):

```bash
uv run np serve                    # or: uv run np install-service
uv run np start-spotify-session    # separate terminal tab; polls Spotify into spotify_* files
# check: open http://127.0.0.1:8976/spotify/
uv run np stop-spotify-session     # stops worker only; not `serve` / LaunchAgent
```

The HTTP server (`serve` or LaunchAgent) must be running for `/spotify/*` URLs. The session command only starts the file-writing worker.

### Viewer

- **`/` (main dashboard):** uses Server-Sent Events on `/events`, with a 5-second `/current` poll as backup.
- **`/spotify/` (Spotify dashboard):** polls `/spotify/current` every 5 seconds (no SSE).

### Debugging

- **Port in use:** stop the agent (`uv run np stop-service`) or bind another port: `uv run np serve --port 8977`.
- **Wrong provider or silent failures:** stop background service, run foreground `serve`, watch the terminal.
- **Service not reachable:** `curl http://127.0.0.1:8976/health`
- **Need paths/URLs again:** `uv run np status`

## Smoke test

```bash
python3 scripts/smoke_install.py
python3 scripts/smoke_install.py --with-service   # also installs/refreshes LaunchAgent; leaves it running
```

After `--with-service`, stop the agent with `uv run np uninstall-service` (or `stop-service` to pause without removing the plist).

## OBS

Pick one primary integration path:

| Goal | Recommended path |
| --- | --- |
| Artwork + text in one Browser Source | `/overlay` URL |
| Most stable local setup | File sources (`current_song.txt` + `current_artwork.png`) |
| Push into named OBS inputs | WebSocket (`OBSWS_*` in `config.env`) |

Start with integration values from the CLI:

```bash
uv run np status
```

Use `obs.browser_overlay_url`, `obs.spotify_overlay_url`, and `obs.files.*` from that JSON in OBS.

### Browser Source (overlay URL)

1. Start the service: `uv run np serve` or `uv run np install-service`.
2. OBS → **Sources → + → Browser**.
3. URL: `http://127.0.0.1:8976/overlay` (or `obs.browser_overlay_url` from `status`).
4. Set width/height for your scene (for example 760×184).

Spotify-only overlay **(unstable):** `http://127.0.0.1:8976/spotify/overlay` after `uv run np start-spotify-session`.

### Overlay customization

#### Quick recipes

| Goal | URL |
| --- | --- |
| Compact default | `http://127.0.0.1:8976/overlay?preset=compact` |
| TV mode | `http://127.0.0.1:8976/overlay?preset=tv` |
| TV mode, one line | `http://127.0.0.1:8976/overlay?preset=tv&max_lines=1` |
| TV mode, hide status | `http://127.0.0.1:8976/overlay?preset=tv&hide_status=1` |
| Lighter panel | `http://127.0.0.1:8976/overlay?preset=tv&panel_opacity=0.50` |

Same query flags work on `/spotify/overlay`.

#### URL flags

| Flag | Example | Env default | Purpose |
| --- | --- | --- | --- |
| `preset` | `?preset=tv` | `NOW_PLAYING_OVERLAY_PRESET` | `compact` or `tv` layout |
| `hide_status` | `?hide_status=1` | `NOW_PLAYING_OVERLAY_HIDE_STATUS` | Hide PLAYING/IDLE label |
| `max_lines` | `?max_lines=1` | `NOW_PLAYING_OVERLAY_MAX_LINES` | Clamp lines (1–3) |
| `panel_opacity` | `?panel_opacity=0.50` | `NOW_PLAYING_OVERLAY_PANEL_OPACITY` | Panel opacity (0.20–0.95) |

URL flags override env defaults.

#### Custom HTML templates

1. Copy bundled templates:

```bash
mkdir -p "$HOME/.config/now-playing/templates"
cp now_playing/templates/dashboard.html "$HOME/.config/now-playing/templates/"
cp now_playing/templates/overlay.html "$HOME/.config/now-playing/templates/"
```

2. Edit files; keep required placeholders (listed below).
3. Set in `config.env`:

```bash
NOW_PLAYING_TEMPLATE_DIR=/Users/you/.config/now-playing/templates
```

4. Restart (`uv run np restart-service` or restart `serve`).

**Template precedence:** `NOW_PLAYING_*_TEMPLATE_PATH` → `NOW_PLAYING_TEMPLATE_DIR` → bundled `now_playing/templates/` → in-code fallback. Invalid custom templates log a warning and fall back.

**Required placeholders**

- `dashboard.html`: `__ENDPOINT_PREFIX__`, `__USE_SSE__`
- `overlay.html`: above plus `__OVERLAY_PRESET__`, `__OVERLAY_STATUS_CLASS__`, `__OVERLAY_MAX_LINES__`, `__OVERLAY_PANEL_OPACITY__`

### File sources (text + image)

1. `uv run np status` → copy `obs.files.song` and `obs.files.artwork`.
2. OBS → **Text** source → **Read from file** → song path.
3. OBS → **Image** source → artwork path.

Works without OBS WebSocket enabled.

### WebSocket push (optional)

In `config.env`:

```bash
OBSWS_ENABLED=1
OBSWS_HOST=localhost
OBSWS_PORT=4455
OBSWS_PASSWORD=your-password
OBSWS_IMAGE_INPUT_NAME=NPImage
OBSWS_TEXT_INPUT_NAME=NPText
OBSWS_TEXT_FIELD=text
```

Enable OBS WebSocket with matching host/port/password. Create inputs with those names. Run `sync` or `serve`; updates push when the track or artwork changes.

## Configuration

Settings load from repo-root [`config.env`](config.env) via `load_config_env()`.

**Precedence** (highest wins):

1. Variables already in your shell environment
2. `config.env` (only fills keys that are not already set)
3. Built-in defaults in code

`config.env` is gitignored. Copy [`config.env.example`](config.env.example) — never commit secrets.

| Variable | Purpose |
| --- | --- |
| `NOW_PLAYING_SOURCE` | `auto`, `apple_music`, or `spotify`. **`auto`:** Apple Music when playing → else Spotify when playing → else Apple Music if running → else Spotify. **`spotify` and Spotify branches are less reliable in background** (AppleScript). |
| `NOW_PLAYING_IDLE_TEXT` | Text when idle; empty string = empty file |
| `NOW_PLAYING_HOST` | HTTP bind address (default `127.0.0.1`) |
| `NOW_PLAYING_PORT` | HTTP port (default `8976`) |
| `NOW_PLAYING_OVERLAY_PRESET` | Default overlay: `compact` or `tv` |
| `NOW_PLAYING_OVERLAY_HIDE_STATUS` | `1` hide status label; `0` show |
| `NOW_PLAYING_OVERLAY_MAX_LINES` | Line clamp 1–3 |
| `NOW_PLAYING_OVERLAY_PANEL_OPACITY` | 0.20–0.95 |
| `NOW_PLAYING_DASHBOARD_TEMPLATE_PATH` | Override dashboard HTML file |
| `NOW_PLAYING_OVERLAY_TEMPLATE_PATH` | Override overlay HTML file |
| `NOW_PLAYING_TEMPLATE_DIR` | Directory with `dashboard.html` / `overlay.html` |
| `NOW_PLAYING_SPOTIFY_TERMINAL` | `auto`, `iterm`, or `terminal` for Spotify session |
| `INTERVAL_SECONDS` | Poll interval for `serve` / LaunchAgent |
| `PYTHON_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `NOW_PLAYING_LAUNCHD_LABEL` | LaunchAgent plist label |
| `OBSWS_ENABLED` | Set to `1` to enable WebSocket push; `0` or unset disables push |
| `OBSWS_HOST` / `OBSWS_PORT` / `OBSWS_PASSWORD` | OBS WebSocket |
| `OBSWS_IMAGE_INPUT_NAME` | Image input for artwork |
| `OBSWS_TEXT_INPUT_NAME` | Optional text input (blank = use file only) |
| `OBSWS_TEXT_FIELD` | Text field on the OBS input |

Full variable list and Python surfaces: [docs/integration-contract.md](docs/integration-contract.md).

## Commands

Global pattern:

```bash
uv run np [--source auto|apple_music|spotify] [--idle-text "…"] <command>
```

### Common tasks

| Goal | Command | What you get |
| --- | --- | --- |
| See current track (live) | `uv run np` | JSON on stdout; does not write `_data/` |
| Run locally | `uv run np serve` | HTTP on `127.0.0.1:8976` |
| Install background service | `uv run np install-service` | LaunchAgent running |
| Check service + OBS hints | `uv run np status` | JSON status |
| Update files once | `uv run np sync` | `_data/` written |
| Create config file | `uv run np init-config` | `config.env` from example |
| Follow logs | `uv run np tail --follow` | `_logs/launchd.log` stream |

### Reference

| Command | What it does |
| --- | --- |
| `current --format json` | Live track JSON + provider diagnostics (does not write `_data/`) |
| `current --format text` | Live four-line text (idle → `NOW_PLAYING_IDLE_TEXT`) |
| `artwork` | Artwork path on stdout, if any |
| `sync` | One poll; updates `_data/` and OBS if enabled |
| `serve [--host] [--port] [--interval-seconds]` | Foreground poll + HTTP |
| `init-config` | Creates `config.env` if missing |
| `install-service` | Writes plist and starts agent |
| `start-service` / `stop-service` / `restart-service` | Control installed agent |
| `status` | Install/runtime JSON + OBS block (exit `0` if plist exists, `1` if not installed) |
| `tail [--lines N] [--follow]` | LaunchAgent log (default `--lines 40`) |
| `start-spotify-session [--terminal]` | Spotify worker in Terminal/iTerm **(unstable)** |
| `stop-spotify-session` | Stop Spotify worker (unstable path only) |
| `uninstall-service` | Stop and remove plist |

### Examples

```bash
uv run np --source apple_music current --format text
uv run np serve --interval-seconds 2
uv run np install-service && uv run np status
```

## API examples (curl)

Same paths as [HTTP routes](#http-routes). Default host/port shown.

```bash
curl http://127.0.0.1:8976/health
curl http://127.0.0.1:8976/current
curl http://127.0.0.1:8976/current.txt
curl -I http://127.0.0.1:8976/current_artwork.png
open http://127.0.0.1:8976/
curl http://127.0.0.1:8976/spotify/current    # when Spotify session is running
```

## Docs map

| Document | Audience | Use when |
| --- | --- | --- |
| [README.md](README.md) (this file) | Operators, stream setup | Install, run, OBS, recovery |
| [docs/integration-contract.md](docs/integration-contract.md) | Contributors, integrators | CLI/HTTP/files/env/Python contract |
| [AGENTS.md](AGENTS.md) | Coding agents | Stack, tests, branch naming |
| [TOOL_DOCS_NOTES.md](TOOL_DOCS_NOTES.md) | Doc authors | Structure and quality checklist |
| [config.env.example](config.env.example) | First-time setup | Annotated defaults |

When you add commands, routes, env vars, or side effects, update this README and [docs/integration-contract.md](docs/integration-contract.md).

# Integration contract (`np`)

Developer reference for public interfaces. Use this when changing CLI commands, HTTP routes, `_data/*` layout, env vars, or Python exports — keep it in sync with behavior and tests.

**Operators** (install, OBS, recovery): [README.md](../README.md).

---

## Quick navigation

| Section | Read when |
| --- | --- |
| [Entry points](#entry-points) | Choosing `np` vs `import np_service` vs legacy `python -m now_playing` |
| [CLI](#cli-np) | Adding or renaming commands |
| [HTTP API](#http-api-serve) | Route parity (especially before FastAPI migration) |
| [File outputs](#file-outputs-_data) | Changing sync materialization |
| [Environment variables](#environment-variables) | Config surface / precedence |
| [Python: facade](#python-api-np_service-facade) | Tests and backward-compatible imports |
| [Python: legacy](#python-api-not-on-the-facade) | Avoid extending; plan deprecation |
| [Contract tests](#contract-tests) | Pre-merge checklist |

---

## Entry points

| Invocation | Facade? | Notes |
| --- | --- | --- |
| `uv run np …` | Yes | [`pyproject.toml`](../pyproject.toml) → `np_service:cli` |
| `python np_service.py …` | Yes | Same entrypoint |
| `import np_service` | Yes | Re-exports from `now_playing/` (`__all__`) |
| `python -m now_playing …` | No | Legacy CLI — different files and `TrackInfo` |
| `import now_playing.…` | No | Implementation modules |

CLI dispatch: [`now_playing/cli.py`](../now_playing/cli.py) imports `np_service` at runtime so callers can patch the facade in tests.

---

## CLI (`np`)

### Global flags

| Flag | Values | Default |
| --- | --- | --- |
| `--source` | `auto`, `apple_music`, `spotify` | `NOW_PLAYING_SOURCE` or `auto` |
| `--idle-text` | string | `NOW_PLAYING_IDLE_TEXT` or `""` |

Default subcommand when omitted: `current --format json` (live query; does not write `_data/`).

### `current` vs `sync`

| Command | Reads players | Writes `_data/` | OBS WebSocket |
| --- | --- | --- | --- |
| `current` | Yes (live) | No | No |
| `sync` | Yes | Yes (`current_*` namespace) | Yes, if `OBSWS_ENABLED=1` and track/artwork changed |

### Commands

| Command | Purpose |
| --- | --- |
| `current [--format json\|text]` | Live track (default command; no file write) |
| `artwork` | Artwork path on stdout |
| `sync` | Write `_data/*`, OBS if enabled |
| `serve` | Poll loop + HTTP API |
| `init-config` | Create `config.env` from example |
| `install-service` / `uninstall-service` | LaunchAgent install/remove |
| `start-service` / `stop-service` / `restart-service` | Control installed agent |
| `status` | JSON: `installed`, `loaded`, `running`, `pid`, `url`, `obs` (exit `0` if plist exists, `1` if not) |
| `tail [--lines N] [--follow]` | `_logs/launchd.log` (default `N=40`) |
| `start-spotify-session [--terminal]` | Terminal Spotify worker (**unstable**) |
| `spotify-session-serve` | Internal: Spotify poll loop (**unstable**) |
| `stop-spotify-session` | Stop terminal worker (**unstable** path) |

### `serve` flags

| Flag | Default |
| --- | --- |
| `--host` | `NOW_PLAYING_HOST` or `127.0.0.1` |
| `--port` | `NOW_PLAYING_PORT` or `8976` |
| `--interval-seconds` | `INTERVAL_SECONDS` or `5` |

---

## HTTP API (`serve`)

Implementation: [`now_playing/http_server.py`](../now_playing/http_server.py) (stdlib).  
Default: `http://127.0.0.1:8976`.

### Core routes

| Method | Path | Response |
| --- | --- | --- |
| GET | `/` | Dashboard HTML (SSE on `/events` + 5s `/current` poll fallback) |
| GET | `/overlay` | OBS overlay HTML |
| GET | `/events` | SSE (`event: now_playing`) |
| GET | `/health` | `{"status":"ok"}` |
| GET | `/current` | Track JSON |
| GET | `/current.txt` | Plain text |
| GET | `/artwork` | `{"artwork_path": …}` |
| GET | `/current_artwork.png` | PNG (`Cache-Control: no-store`) |

### Spotify namespace (file-backed, **unstable**)

Status: **unstable** — dual-process design (HTTP server + Terminal worker), AppleScript polling, and `/spotify/*` routes may change or break without notice.

Requires:

1. HTTP server: `serve` or LaunchAgent (`install-service`)
2. Worker: `start-spotify-session` (writes `spotify_*` under `_data/`)

`/spotify/*` routes read files only (`live_fallback=False`); they do not poll Spotify directly.

| Method | Path | Response |
| --- | --- | --- |
| GET | `/spotify`, `/spotify/` | Spotify dashboard (polls `/spotify/current` every 5s; no SSE) |
| GET | `/spotify/overlay` | Spotify overlay |
| GET | `/spotify/current` | JSON from `spotify_current_track.json` |
| GET | `/spotify/current.txt` | Plain text |
| GET | `/spotify/artwork` | Artwork path JSON |
| GET | `/spotify/current_artwork.png` | PNG |

### Overlay query params

Both `/overlay` and `/spotify/overlay`: `preset`, `hide_status`, `max_lines`, `panel_opacity`.  
Env defaults: `NOW_PLAYING_OVERLAY_*`. URL wins over env.

---

## File outputs (`_data/`)

Relative to repo root. Written by `sync` / polling in `serve`.

### Current namespace

| File | Content |
| --- | --- |
| `current_song.txt` | Display text |
| `current_track.json` | Payload + `providers` |
| `current_artwork.png` | Artwork copy |
| `now_playing_artworks.txt` | Artwork path line(s) |
| `sync_state.json` | Last fingerprint |

### Spotify namespace (**unstable**)

Written by `start-spotify-session` / `spotify-session-serve`, not the main LaunchAgent poll alone.

| File | Content |
| --- | --- |
| `spotify_current_song.txt` | Display text |
| `spotify_current_track.json` | Payload |
| `spotify_current_artwork.png` | Artwork |
| `spotify_now_playing_artworks.txt` | Artwork paths |
| `spotify_sync_state.json` | Fingerprint |
| `spotify-session.pid` | Terminal worker PID |

Cache: `~/.now-playing/artwork-cache/`.

---

## Environment variables

Loaded from repo-root `config.env` with `setdefault` (does not override existing shell env).

**`NOW_PLAYING_SOURCE=auto` selection** (in [`providers/auto.py`](../now_playing/providers/auto.py)):

1. Apple Music playing → Apple Music track
2. Else Spotify playing → Spotify track
3. Else Apple Music not `not_running` → Apple Music track (idle/paused)
4. Else → Spotify track

| Variable | Purpose |
| --- | --- |
| `NOW_PLAYING_SOURCE` | `auto`, `apple_music`, or `spotify` |
| `NOW_PLAYING_IDLE_TEXT` | Idle display text |
| `NOW_PLAYING_HOST` / `NOW_PLAYING_PORT` | HTTP bind |
| `INTERVAL_SECONDS` | Poll interval |
| `PYTHON_LOG_LEVEL` | Logging |
| `NOW_PLAYING_LAUNCHD_LABEL` | LaunchAgent label |
| `NOW_PLAYING_SPOTIFY_TERMINAL` | `auto`, `iterm`, `terminal` |
| `NOW_PLAYING_OVERLAY_*` | Overlay defaults |
| `NOW_PLAYING_*_TEMPLATE_PATH`, `NOW_PLAYING_TEMPLATE_DIR` | HTML overrides |
| `OBSWS_*` | OBS WebSocket push (`OBSWS_ENABLED` must be exactly `1`) |

**LaunchAgent plist:** `install-service` embeds a snapshot of selected keys via `env_subset()` in [`launchd_service.py`](../now_playing/launchd_service.py): `NOW_PLAYING_SOURCE`, `NOW_PLAYING_IDLE_TEXT`, `NOW_PLAYING_HOST`, `NOW_PLAYING_PORT`, `INTERVAL_SECONDS`, `PYTHON_LOG_LEVEL`, `OBSWS_*`. Overlay/template vars are not in the plist; they load from `config.env` on each `serve` start via `load_config_env()`. Plist `EnvironmentVariables` win over `config.env` for keys present in both.

Annotated defaults: [`config.env.example`](../config.env.example). Operator summary: [README → Configuration](../README.md#configuration).

---

## Python API: `np_service` facade

[`np_service.py`](../np_service.py) — authoritative list is `__all__`. Grouped summary:

| Area | Key symbols |
| --- | --- |
| CLI | `cli`, `main`, `build_parser`, `current_settings` |
| Models | `TrackInfo`, `ProviderSnapshot`, `ProviderError` |
| Config | `load_config_env`, `configure_logging`, `DEFAULT_SOURCE`, `DEFAULT_IDLE_TEXT` |
| Paths | `repo_dir`, `data_dir`, `logs_dir`, `namespaced_*`, `current_*_file`, … |
| I/O | `write_*_if_changed`, `copy_file_if_changed`, `remove_file_if_exists` |
| Templates | `load_html_template`, `render_dashboard`, `render_overlay` |
| Providers | `get_*_track`, `select_track`, `select_track_with_diagnostics`, … |
| Sync | `sync`, `materialize_outputs`, `read_current_payload`, `save_state`, … |
| OBS | `obs_enabled`, `update_obs` |
| HTTP | `NowPlayingHTTPServer`, `RequestHandler`, `run_server` |
| LaunchAgent | `install_service`, `service_status`, `tail_service_log`, … |
| Spotify session | `start_spotify_session`, `run_spotify_session`, … |

Prefer `import np_service` in tests and scripts unless you need a specific submodule.

---

## Python API: not on the facade

**Do not extend for new features.** Planned cleanup in provider unification work.

| Surface | Location | Notes |
| --- | --- | --- |
| Legacy CLI | [`now_playing/__main__.py`](../now_playing/__main__.py) | `applemusic`/`spotify`, `--info`/`--image`/`--update-obs` |
| Legacy providers | [`now_playing/providers/legacy.py`](../now_playing/providers/legacy.py) | `AppleMusicProvider`, `SpotifyProvider`, `LegacyTrackInfo` |
| Legacy I/O | [`now_playing/files.py`](../now_playing/files.py), [`obs_client.py`](../now_playing/obs_client.py) | Separate from np sync path |

Legacy writes `apple_current_song.txt`, `spotify_current_song.txt`, `apple_now_playing_artworks.txt`, and `spotify_now_playing_artworks.txt` — not the `current_*` / `spotify_*` layout used by `np`.

---

## Module map

| Module | Responsibility |
| --- | --- |
| `now_playing/cli.py` | CLI dispatch |
| `now_playing/models.py` | Domain types |
| `now_playing/paths.py` | Repo / `_data` paths |
| `now_playing/fs.py` | Atomic writes |
| `now_playing/config_env.py` | `config.env` loader |
| `now_playing/state.py` | Sync state persistence |
| `now_playing/providers/{apple,spotify,auto}.py` | Provider I/O + selection |
| `now_playing/sync_service.py` | Sync pipeline |
| `now_playing/obs_integration.py` | OBS WebSocket (np path) |
| `now_playing/http_server.py` | Stdlib HTTP + SSE |
| `now_playing/dashboard_html.py` | HTML render |
| `now_playing/launchd_service.py` | LaunchAgent |
| `now_playing/spotify_session.py` | Terminal Spotify worker |
| `np_service.py` | Facade re-exports |

---

## Contract tests

Before merging interface changes:

```bash
uv run pytest
python3 scripts/smoke_install.py
python3 scripts/smoke_install.py --with-service   # macOS; optional
```

HTTP changes: assert routes in [`tests/test_np_service.py`](../tests/test_np_service.py); spot-check with `curl -I` on artwork and `/health`.

When updating this contract, update [README.md](../README.md) operator sections if user-visible behavior changed.

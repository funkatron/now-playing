# Changelog

All notable changes to this project are documented here. Version numbers match [GitHub releases](https://github.com/funkatron/now-playing/releases).

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html) while on `0.x`.

## [Unreleased]

## [0.2.0] - 2026-06-02

First release after v0.1.0. The project is a **uv-backed `np` CLI** with optional LaunchAgent, HTTP API, and OBS integration.

### Added

- Unified CLI (`uv run np`): `serve`, `sync`, `current`, `init-config`, LaunchAgent install/status/stop/uninstall
- Providers: Apple Music, Spotify desktop, and `auto` source selection
- HTTP server on `127.0.0.1:8976` (health, current JSON/text, artwork, browser viewer, transparent OBS overlay)
- OBS WebSocket push when `OBSWS_ENABLED=1`; customizable overlay templates
- `now_playing/` package with `np_service` CLI facade
- Atomic writes and namespaced `_data/` outputs per provider
- Pytest suite and `scripts/smoke_install.py` local install checks

### Changed

- Packaging and dependencies managed with **uv** (`uv sync`, `uv.lock`)
- Operator docs refreshed (README, integration contract)

### Removed

- Per-app wrapper scripts and the standalone `update.sh` workflow (replaced by `uv run np`)

### Breaking

- Requires [uv](https://github.com/astral-sh/uv) on macOS; upgrade path in [README — Start here](README.md#start-here)

### Notes

- Spotify `/spotify/*` HTTP routes and `start-spotify-session` remain experimental; Apple Music + LaunchAgent is the stable path.

[0.2.0]: https://github.com/funkatron/now-playing/releases/tag/v0.2.0

## [0.1.0] - 2024-02-20

Initial public release.

### Added

- Apple Music.app polling on macOS
- Shell-based updaters writing local now-playing files for OBS

[0.1.0]: https://github.com/funkatron/now-playing/releases/tag/v0.1.0

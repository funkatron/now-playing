# Agent notes (now-playing)

## Stack

- **Python** 3.9+; packaging in [`pyproject.toml`](pyproject.toml).
- **CLI / env**: use **`uv`** (`uv sync`, `uv run np …`). Do not assume global `pip install` unless the user says so.
- **Layout**: implementation in [`now_playing/`](now_playing/); backward-compatible facade in [`np_service.py`](np_service.py).

## Verify changes

```bash
uv run pytest
python3 scripts/smoke_install.py
python3 scripts/smoke_install.py --with-service   # optional; macOS + LaunchAgent
```

## Documentation map

| File | Update when |
| --- | --- |
| [`README.md`](README.md) | Operator-facing behavior, OBS setup, recovery, env summary |
| [`docs/integration-contract.md`](docs/integration-contract.md) | CLI subcommands, HTTP routes, `_data/*`, Python exports |
| [`config.env.example`](config.env.example) | New/changed env vars (with comments) |
| [`TOOL_DOCS_NOTES.md`](TOOL_DOCS_NOTES.md) | Doc structure standards (rare) |

**Style:** README = task-first operator guide. Integration contract = exhaustive dev reference. Do not duplicate long tables in both — cross-link instead.

When editing README, follow [`TOOL_DOCS_NOTES.md`](TOOL_DOCS_NOTES.md) (quick start before reference, side effects, recovery).

## Scope

- Minimal, task-focused code changes; match existing module style.
- macOS only. **LaunchAgent** refers to the OS background job (`uv run np install-service`), not AI agents.

**Behavior (do not contradict in docs):**

- `uv run np` (no subcommand) = live `current` JSON; does not write `_data/`.
- `sync` / `serve` / LaunchAgent write `current_*` under `_data/`.
- Spotify `/spotify/*` HTTP needs `serve` or LaunchAgent **and** `start-spotify-session` — **unstable** (file-backed routes; dual-process).
- `OBSWS_ENABLED` must be exactly `1` to enable WebSocket push.

## Branches

- Branch from **`main`**.
- Name feature branches: `feature/issue###-issue-title`.

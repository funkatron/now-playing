# Agent notes (now-playing)

## Stack

- **Python** 3.12+; dependencies and packaging in [`pyproject.toml`](pyproject.toml).
- **CLI / env**: use **`uv`** (`uv sync`, `uv run np …`). Do not assume a global `pip install` unless the user says so.

## Verify changes

```bash
uv run pytest
```

Smoke checks (local install and optional `launchd` + HTTP):

```bash
python3 scripts/smoke_install.py
python3 scripts/smoke_install.py --with-service
```

## Documentation

- User-facing and operator docs live in [`README.md`](README.md).
- When editing README, follow the structure and checklist in [`TOOL_DOCS_NOTES.md`](TOOL_DOCS_NOTES.md) (quick start before reference, explicit interfaces and side effects, recovery).

## Scope

- Prefer minimal, task-focused changes; match existing style in [`np_service.py`](np_service.py) and [`now_playing/`](now_playing/).
- macOS-only; scripts like `install-launch-agent.sh` refer to **LaunchAgent** (OS), not AI agents.

## Branches

- Branch from **`main`**.
- Name feature branches: `feature/issue###-issue-title` (issue number + short kebab-case title).

# Tool documentation standards (now-playing)

Use this when writing or revising docs for the `np` CLI and local service.

**Goal:** a reader can install, run, verify, and recover without reading source code.

## Project doc roles

| File | Audience | Must answer |
| --- | --- | --- |
| [README.md](README.md) | Operators, OBS setup | What to run first; how to know it works; how to stop |
| [docs/integration-contract.md](docs/integration-contract.md) | Contributors, integrators | Full CLI/HTTP/files/env/Python contract |
| [config.env.example](config.env.example) | First-time config | Annotated defaults and precedence |
| [AGENTS.md](AGENTS.md) | Coding agents | Stack, tests, which doc to update |

Keep operator content in README. Keep exhaustive reference in the integration contract. Cross-link; do not copy large tables twice.

## Required reader questions

Every doc pass should make these obvious:

1. What command do I run first?
2. What does success look like?
3. Which URL is for humans vs machines vs OBS?
4. Does this command leave something running in the background?
5. How do I stop it?
6. Where are logs (`uv run np tail`)?
7. What if port 8976 is in use?

## README structure (this repo)

Use this order:

1. Short summary + what you get
2. Requirements
3. Start here (one default command path)
4. How do I… (task table)
5. Outputs and HTTP endpoints
6. Foreground vs background (+ Spotify session caveat)
7. OBS (file / browser / websocket paths)
8. Configuration (precedence + variable table)
9. Commands (common tasks table, then reference)
10. curl examples (short)
11. Docs map

Put recovery steps near the modes they apply to (foreground vs LaunchAgent).

## Configuration docs

Document explicitly:

- **Precedence:** shell env → `config.env` (`setdefault`) → code defaults
- **`config.env` is gitignored** — no secrets in git
- Optional vars commented out in `config.env.example`
- Impact of each variable, not just the name

## Side effects to call out

- `install-service` writes `~/Library/LaunchAgents/*.plist` and starts the agent
- `serve` and the agent write under `_data/` and `_logs/launchd.log`
- `OBSWS_ENABLED=1` pushes to OBS over WebSocket when track or artwork changes (`sync` / `serve` poll)
- `start-spotify-session` opens Terminal/iTerm with a background poll loop (**unstable** path)

## Honest platform notes

- Apple Music: best fit for LaunchAgent background path
- Spotify: **unstable** — `start-spotify-session` + `/spotify/*` namespace; avoid for production streams
- Legacy `python -m now_playing` exists; prefer `uv run np` in docs

## Revision workflow

1. Read `uv run np --help` and [`config.env.example`](config.env.example).
2. Compare to [docs/integration-contract.md](docs/integration-contract.md).
3. Rewrite start path if first-run is unclear.
4. Add or update the **How do I…** task table when adding commands.
5. Update integration contract for any public interface change.
6. Run a skeptical read-through (impatient new user).
7. Polish prose — direct verbs, named paths, no filler.

## Quality checklist

- [ ] One-command default in Start here
- [ ] How do I… / common tasks table present
- [ ] Stop + verify steps documented
- [ ] Config precedence documented
- [ ] Side effects explicit for service install
- [ ] Recovery for port conflict and wrong provider
- [ ] integration-contract.md updated for interface changes
- [ ] No contradictory paths between README and contract

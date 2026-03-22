#!/usr/bin/env python3
"""Smoke-test the local installation path for the now-playing service.

This script is for operator-style verification, not pytest.

It checks that:
- `uv sync` succeeds
- the packaged `np` CLI is runnable
- `np sync` writes the expected flat files under `_data/`

Optionally, it can also install or refresh the per-user `launchd` job and
verify that the local HTTP API responds on `127.0.0.1:8976`.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "_data"
DEFAULT_HEALTH_URL = "http://127.0.0.1:8976/health"
DEFAULT_CURRENT_URL = "http://127.0.0.1:8976/current"


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print(f"$ {' '.join(command)}")
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )


def require_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Expected file to exist: {path}")


def validate_json_output(raw: str) -> dict:
    payload = json.loads(raw)
    for key in ("source", "state", "title", "artist", "album", "artwork_path", "updated_at"):
        if key not in payload:
            raise RuntimeError(f"Missing key in JSON payload: {key}")
    return payload


def smoke_local() -> None:
    print("== Local install checks ==")
    print("This will sync dependencies, ensure config.env exists, run the packaged CLI, and verify local output files.")
    run(["uv", "sync"])
    run(["uv", "run", "np", "init-config"])

    current = run(["uv", "run", "np", "current", "--format", "json"], capture=True)
    validate_json_output(current.stdout)

    sync = run(["uv", "run", "np", "sync"], capture=True)
    sync_payload = json.loads(sync.stdout)
    if "track" not in sync_payload:
        raise RuntimeError("Sync output did not include track payload")

    require_file(DATA_DIR / "current_song.txt")
    require_file(DATA_DIR / "current_track.json")
    require_file(DATA_DIR / "sync_state.json")
    print("Local install checks passed.")


def smoke_service() -> None:
    print("== Service checks ==")
    print(
        "This will install or refresh the per-user launchd job, then query the local HTTP API. "
        "The service is left running afterward."
    )
    run(["uv", "run", "np", "install-service"])

    health_payload = None
    for _ in range(10):
        try:
            health = run(["curl", "-s", DEFAULT_HEALTH_URL], capture=True)
            health_payload = json.loads(health.stdout)
            break
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            time.sleep(0.5)

    if not health_payload or health_payload.get("status") != "ok":
        raise RuntimeError("Health endpoint did not return ok")

    current = run(["curl", "-s", DEFAULT_CURRENT_URL], capture=True)
    validate_json_output(current.stdout)
    print("Service checks passed.")
    print("The launchd service is still installed and running.")
    print("Stop it with: uv run np uninstall-service")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run an operator-facing smoke test for the now-playing install flow. "
            "By default this validates local CLI setup and output-file generation. "
            "Use --with-service to also install/refresh the launchd service, verify the local HTTP API, "
            "and leave the service running afterward."
        )
    )
    parser.add_argument(
        "--with-service",
        action="store_true",
        help=(
            "Also install or refresh the per-user launchd service and verify "
            "the local HTTP API on 127.0.0.1:8976."
        ),
    )
    args = parser.parse_args(argv)

    smoke_local()
    if args.with_service:
        smoke_service()

    print("Smoke install checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

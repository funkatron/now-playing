#!/usr/bin/env python3
import os
import sys
import subprocess


def main() -> int:
    # Delegate to unified CLI: python -m now_playing spotify [--info|--image|--update-obs]
    args = sys.argv[1:]
    cmd = [sys.executable, "-m", "now_playing", "spotify"] + args
    env = os.environ.copy()
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
"""Load config.env into os.environ."""

import os

from now_playing.paths import config_env_file


def load_config_env() -> None:
    path = config_env_file()
    if not path.exists():
        return

    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


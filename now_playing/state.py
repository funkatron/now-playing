"""Sync state persistence."""

import json

from now_playing.fs import write_json_if_changed
from now_playing.logging_config import LOGGER
from now_playing.paths import namespaced_state_file


def read_previous_state(namespace: str = "current") -> dict:
    path = namespaced_state_file(namespace)
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        LOGGER.warning("Ignoring invalid state file at %s", path)
        return {}


def save_state(payload: dict, namespace: str = "current") -> None:
    write_json_if_changed(namespaced_state_file(namespace), payload)

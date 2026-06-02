"""Small shared helpers."""

import re
from datetime import datetime, timezone

from now_playing.logging_config import PLAYING_STATE_CODE


def safe_filename(value: str) -> str:
    return re.sub(r"[^\w-]", "", value)

def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def is_playing_state(player_state) -> bool:
    if player_state == PLAYING_STATE_CODE:
        return True

    if isinstance(player_state, str):
        return player_state.strip().lower() == "playing"

    return str(player_state or "").strip().lower() == "playing"

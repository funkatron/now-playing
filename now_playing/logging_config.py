"""Logging and module-level defaults."""

import logging
import os

LOGGER = logging.getLogger("now_playing")

PLAYING_STATE_CODE = 1800426320
DEFAULT_SOURCE = os.environ.get("NOW_PLAYING_SOURCE", "auto")
DEFAULT_IDLE_TEXT = os.environ.get("NOW_PLAYING_IDLE_TEXT", "")


def configure_logging() -> None:
    level_name = os.environ.get("PYTHON_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")

"""OBS WebSocket integration."""

import os

from now_playing.logging_config import LOGGER
from now_playing.models import TrackInfo
from now_playing.paths import current_artwork_file


def obs_enabled() -> bool:
    return os.environ.get("OBSWS_ENABLED", "0") == "1"


def update_obs(track: TrackInfo, display_text: str) -> bool:
    if not obs_enabled():
        LOGGER.debug("Skipping OBS update because OBSWS_ENABLED is not set.")
        return False

    from obswebsocket import obsws, requests

    host = os.environ.get("OBSWS_HOST", "localhost")
    port = int(os.environ.get("OBSWS_PORT", "4455"))
    password = os.environ.get("OBSWS_PASSWORD", "")
    image_input = os.environ.get("OBSWS_IMAGE_INPUT_NAME", "NPImage")
    text_input = os.environ.get("OBSWS_TEXT_INPUT_NAME")
    text_field = os.environ.get("OBSWS_TEXT_FIELD", "text")

    ws = obsws(host, port, password)
    ws.connect()
    try:
        if track.artwork_path and current_artwork_file().exists():
            ws.call(
                requests.SetInputSettings(
                    inputName=image_input,
                    inputSettings={"file": str(current_artwork_file())},
                )
            )

        if text_input:
            ws.call(
                requests.SetInputSettings(
                    inputName=text_input,
                    inputSettings={text_field: display_text},
                )
            )
    finally:
        ws.disconnect()

    LOGGER.debug("Updated OBS for source=%s state=%s", track.source, track.state)
    return True

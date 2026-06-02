"""Sync pipeline: providers -> files -> OBS."""

import json
from dataclasses import asdict
from pathlib import Path

from now_playing.fs import (
    copy_file_if_changed,
    remove_file_if_exists,
    write_json_if_changed,
    write_text_if_changed,
)
from now_playing.logging_config import DEFAULT_SOURCE, LOGGER
from now_playing.models import TrackInfo
from now_playing.obs_integration import update_obs
from now_playing.paths import namespaced_artwork_manifest_file, namespaced_current_artwork_file, namespaced_current_song_file, namespaced_current_track_json_file
from now_playing.providers.auto import select_track_with_diagnostics
from now_playing.state import read_previous_state, save_state
from now_playing.util import iso_now


def materialize_outputs(track: TrackInfo, idle_text: str, namespace: str = "current") -> dict:
    display_text = track.to_text(idle_text)
    artwork_changed = False
    if track.artwork_path:
        artwork_file = namespaced_current_artwork_file(namespace)
        artwork_changed = copy_file_if_changed(Path(track.artwork_path), artwork_file)
        write_text_if_changed(namespaced_artwork_manifest_file(namespace), f"{artwork_file}\n")
        track.artwork_path = str(artwork_file)
    else:
        artwork_changed = remove_file_if_exists(namespaced_current_artwork_file(namespace)) or artwork_changed
        remove_file_if_exists(namespaced_artwork_manifest_file(namespace))

    payload = asdict(track)
    payload["text"] = display_text

    text_changed = write_text_if_changed(namespaced_current_song_file(namespace), display_text)

    return {
        "payload": payload,
        "display_text": display_text,
        "text_changed": text_changed,
        "artwork_changed": artwork_changed,
    }


def sync(source: str, idle_text: str, namespace: str = "current") -> dict:
    track, providers = select_track_with_diagnostics(source)
    previous = read_previous_state(namespace)

    outputs = materialize_outputs(track, idle_text, namespace)
    payload = outputs["payload"]
    payload["providers"] = providers

    normalized_track = dict(track.fingerprint())
    normalized_track["artwork_path"] = payload["artwork_path"]

    track_changed = previous.get("track") != normalized_track
    if not track_changed and previous.get("updated_at"):
        payload["updated_at"] = previous["updated_at"]

    json_changed = write_json_if_changed(namespaced_current_track_json_file(namespace), payload)

    obs_updated = False
    if track_changed or outputs["artwork_changed"]:
        obs_updated = update_obs(track, outputs["display_text"])

    save_state(
        {
            "track": normalized_track,
            "artwork_path": payload["artwork_path"],
            "updated_at": payload["updated_at"],
            "providers": providers,
        },
        namespace,
    )

    return {
        "track": payload,
        "changed": track_changed,
        "text_changed": outputs["text_changed"],
        "json_changed": json_changed,
        "artwork_changed": outputs["artwork_changed"],
        "obs_updated": obs_updated,
    }


def empty_payload(source: str = "unknown") -> dict:
    return {
        "album": "",
        "artist": "",
        "artwork_path": None,
        "providers": {
            source: {
                "detail": "",
                "error": None,
                "source": source,
                "state": "not_running",
                "updated_at": iso_now(),
            }
        } if source != "unknown" else {},
        "source": source,
        "state": "not_running",
        "text": "",
        "title": "",
        "updated_at": iso_now(),
        "year": None,
    }


def read_current_payload(idle_text: str, namespace: str = "current", live_fallback: bool = True) -> dict:
    path = namespaced_current_track_json_file(namespace)
    if path.exists():
        try:
            payload = json.loads(path.read_text())
            if payload.get("artwork_path", "") == "":
                payload["artwork_path"] = None
            return payload
        except json.JSONDecodeError:
            LOGGER.warning("Current track file is invalid; regenerating from live state.")

    if not live_fallback:
        source = "spotify" if namespace == "spotify" else "unknown"
        return empty_payload(source)

    result = sync(DEFAULT_SOURCE, idle_text, namespace)
    return result["track"]

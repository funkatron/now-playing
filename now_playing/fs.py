"""Atomic file writes and copies."""

import json
import shutil
from pathlib import Path


def write_text_if_changed(path: Path, content: str) -> bool:
    existing = path.read_text() if path.exists() else None
    if existing == content:
        return False

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content)
    tmp_path.replace(path)
    return True


def write_json_if_changed(path: Path, payload: dict) -> bool:
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    return write_text_if_changed(path, content)


def copy_file_if_changed(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False

    if destination.exists():
        source_stat = source.stat()
        dest_stat = destination.stat()
        if (
            source_stat.st_size == dest_stat.st_size
            and source_stat.st_mtime_ns == dest_stat.st_mtime_ns
        ):
            return False
        if source.read_bytes() == destination.read_bytes():
            return False

    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copyfile(source, tmp_path)
    tmp_path.replace(destination)
    return True


def remove_file_if_exists(path: Path) -> bool:
    if path.exists():
        path.unlink()
        return True
    return False

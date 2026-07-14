import os
import shutil
from pathlib import Path

from now_playing.fs import copy_file_if_changed


def test_copy_file_if_changed_uses_stat_before_bytes(tmp_path, monkeypatch):
    source = tmp_path / "src.png"
    destination = tmp_path / "dest.png"
    source.write_bytes(b"png-data")
    shutil.copyfile(source, destination)
    timestamp = 1_700_000_000.0
    os.utime(source, (timestamp, timestamp))
    os.utime(destination, (timestamp, timestamp))

    read_calls = []
    original_read_bytes = Path.read_bytes

    def spy_read_bytes(self):
        read_calls.append(self)
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", spy_read_bytes)

    assert copy_file_if_changed(source, destination) is False
    assert read_calls == []

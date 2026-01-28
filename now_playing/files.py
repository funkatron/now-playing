import os
from typing import Optional


def write_if_changed(path: str, new_content: str) -> bool:
    try:
        with open(path, "r") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = None
    if existing == new_content:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(new_content)
    os.replace(tmp_path, path)
    return True


def write_artworks_list(path: str, artwork_paths: list[str]) -> None:
    new_content = "".join(p + "\n" for p in artwork_paths)
    try:
        with open(path, "r") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = None
    if artwork_paths:
        if existing != new_content:
            tmp_path = path + ".tmp"
            with open(tmp_path, "w") as f:
                f.write(new_content)
            os.replace(tmp_path, path)
    else:
        if existing is None:
            open(path, "a").close()



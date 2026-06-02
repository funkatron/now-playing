"""Repository and data path helpers."""

from pathlib import Path


def repo_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    path = repo_dir() / "_data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = repo_dir() / "_logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_env_file() -> Path:
    return repo_dir() / "config.env"


def config_env_example_file() -> Path:
    return repo_dir() / "config.env.example"


def state_file() -> Path:
    return data_dir() / "sync_state.json"


def current_song_file() -> Path:
    return data_dir() / "current_song.txt"


def current_track_json_file() -> Path:
    return data_dir() / "current_track.json"


def artwork_manifest_file() -> Path:
    return data_dir() / "now_playing_artworks.txt"


def current_artwork_file() -> Path:
    return data_dir() / "current_artwork.png"


def spotify_session_pid_file() -> Path:
    return data_dir() / "spotify-session.pid"


def namespaced_state_file(namespace: str = "current") -> Path:
    if namespace == "spotify":
        return data_dir() / "spotify_sync_state.json"
    return state_file()


def namespaced_current_song_file(namespace: str = "current") -> Path:
    if namespace == "spotify":
        return data_dir() / "spotify_current_song.txt"
    return current_song_file()


def namespaced_current_track_json_file(namespace: str = "current") -> Path:
    if namespace == "spotify":
        return data_dir() / "spotify_current_track.json"
    return current_track_json_file()


def namespaced_artwork_manifest_file(namespace: str = "current") -> Path:
    if namespace == "spotify":
        return data_dir() / "spotify_now_playing_artworks.txt"
    return artwork_manifest_file()


def namespaced_current_artwork_file(namespace: str = "current") -> Path:
    if namespace == "spotify":
        return data_dir() / "spotify_current_artwork.png"
    return current_artwork_file()

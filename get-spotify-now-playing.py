#!/usr/bin/env python3
import argparse
import copy
import json
import logging
import os
import re
import urllib.parse
import urllib.request

from ScriptingBridge import SBApplication


def spotify_app_is_playing() -> bool:
    spotify_app = SBApplication.applicationWithBundleIdentifier_("com.spotify.client")
    try:
        state = spotify_app.playerState()
        logging.debug(f"Spotify playerState: {state}")
    except Exception:
        state = None

    # 1800426320 is the 'playing' four-char code ('kPSP') observed in Music; Spotify maps similarly
    if spotify_app.isRunning() and state == 1800426320:
        return True
    return False


def get_current_spotify_track():
    spotify_app = SBApplication.applicationWithBundleIdentifier_("com.spotify.client")
    logging.debug(f"Spotify isRunning: {spotify_app.isRunning()}")
    if spotify_app_is_playing():
        try:
            return spotify_app.currentTrack()
        except Exception as e:
            logging.debug(f"Error getting currentTrack: {e}")
    return None


def get_current_song():
    current_track = get_current_spotify_track()
    if current_track and current_track.name():
        title = current_track.name()
        artist = current_track.artist()
        album = current_track.album()
        # Spotify AppleScript does not expose year; keep an empty 4th line for contract parity
        return f"\"{title}\"\n{artist}\n{album}\n"
    return "Enjoy the silence."


def safe_filename(filename: str) -> str:
    return re.sub(r'[^\w-]', '', filename)


def _download_file(url: str, dest_path: str) -> bool:
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "now-playing/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp, open(dest_path, 'wb') as out:
            out.write(resp.read())
        return True
    except Exception as e:
        logging.debug(f"Failed to download artwork: {e}")
        return False


def get_artworks_for_track() -> list:
    track = get_current_spotify_track()
    if not track:
        # remove file if exists (Spotify-specific)
        now_playing_artworks_file = os.path.join(os.path.dirname(__file__), "_data", "spotify_now_playing_artworks.txt")
        try:
            os.remove(now_playing_artworks_file)
        except FileNotFoundError:
            pass
        return []

    try:
        artwork_url = track.artworkUrl()
    except Exception:
        artwork_url = None

    if not artwork_url:
        return []

    parsed = urllib.parse.urlparse(artwork_url)
    _, ext = os.path.splitext(parsed.path)
    if not ext:
        ext = ".jpg"

    cache_dir = os.path.expanduser(f"~/.now-playing/artwork-cache/")
    cache_filename = safe_filename(f"{getattr(track, 'id', lambda: '')()}_{track.artist()}_{track.album()}_{track.name()}") + ext
    cache_filepath = os.path.join(cache_dir, cache_filename)

    if not os.path.exists(cache_filepath):
        _download_file(artwork_url, cache_filepath)

    artwork_paths = [cache_filepath] if os.path.exists(cache_filepath) else []

    now_playing_artworks_file = os.path.join(os.path.dirname(__file__), "_data", "spotify_now_playing_artworks.txt")
    new_content = "".join(path + "\n" for path in artwork_paths)
    existing_content = None
    try:
        with open(now_playing_artworks_file, "r") as f:
            existing_content = f.read()
    except FileNotFoundError:
        existing_content = None

    if artwork_paths:
        if existing_content != new_content:
            with open(now_playing_artworks_file, "w") as f:
                f.write(new_content)
    else:
        if existing_content is None:
            open(now_playing_artworks_file, "a").close()

    return artwork_paths


current_image_path = None


def update_obs_now_playing_image(image_path: str):
    global current_image_path
    import logging
    logging.basicConfig(level=logging.DEBUG)

    if current_image_path and current_image_path == image_path:
        logging.getLogger().debug("Image path unchanged; skipping OBS update.")
        return

    from obswebsocket import obsws, requests  # type: ignore

    host = "localhost"
    port = 4455
    password = "tH3NSzMaqHHaWExM"

    ws = obsws(host, port, password)
    ws.connect()
    try:
        ws.call(requests.SetInputSettings(
            inputName="NPImageSpotify",
            inputSettings={
                "file": image_path,
            }
        ))
        current_image_path = image_path
    finally:
        ws.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Get the current song playing in Spotify')
    parser.add_argument('--info', action='store_true', help="Get the song info as newline-delimited string.")
    parser.add_argument('--image', action='store_true', help="Get the path to the song cover art.")
    parser.add_argument('--update-obs', action='store_true', help="Update the OBS now playing image.")
    args = parser.parse_args()

    logging.basicConfig(level=os.environ.get("PYTHON_LOG_LEVEL", "WARNING"))

    if args.image:
        song_images = get_artworks_for_track()
        print(song_images[0] if song_images else "")
    elif args.update_obs:
        song_images = get_artworks_for_track()
        if song_images:
            logging.getLogger().debug("Updating OBS now playing image to the current song's album art: %s", song_images[0])
            update_obs_now_playing_image(song_images[0])
        else:
            logging.getLogger().debug("No album art found for the current song.")
    else:
        song_info = get_current_song()
        print(song_info)
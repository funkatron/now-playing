#!/usr/bin/env python3

import argparse
import copy
import logging
import os
import re
import ScriptingBridge

from AppKit import NSBitmapImageRep, NSPNGFileType


def music_app_is_playing() -> bool:
    # Connect to the Music app
    music_app = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Music")

    # Check if something is currently playing
    if music_app.isRunning() and music_app.playerState() == 1800426320: # 1800426320 is the code for playing
        return True

    return False

def get_current_music_app_track() -> ScriptingBridge.SBObject:
    # Connect to the Music app
    music_app = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Music")

    # dump the music_app properties
    logging.debug(f"Music App: {music_app.properties()}")
    # dump the player state
    logging.debug(f"Music App Player State: {music_app.playerState()}")

    # Check if something is currently playing
    if music_app_is_playing():
        return music_app.currentTrack()

    return None


def get_current_song():
    current_track = get_current_music_app_track()
    # Check if something is currently playing
    if current_track and current_track.name():
        title = current_track.name()
        artist = current_track.artist()
        album = current_track.album()
        year = current_track.year()

        return f"\"{title}\"\n{artist}\n{album}\n{year if year else ''}"

    return "Enjoy the silence."


def safe_filename(filename):
    # Remove any characters that are not alphanumeric, underscore, or hyphen
    return re.sub(r'[^\w-]', '', filename)



def get_artworks_for_track() -> list:
    track = get_current_music_app_track()
    if not track:
        # Ensure Apple artworks file exists as empty when no track
        now_playing_artworks_file = os.path.join(os.path.dirname(__file__), "_data", "apple_now_playing_artworks.txt")
        try:
            # Create empty file if missing
            open(now_playing_artworks_file, "a").close()
        except Exception:
            pass
        return []

    artworks = []
    artwork_paths = []
    for artwork in track.artworks():
        if artwork.data():
            artworks.append(artwork.data())
            # Convert the NSImage to a bitmap representation
            bitmap_rep = NSBitmapImageRep.imageRepWithData_(artwork.data().TIFFRepresentation())
            # Convert the bitmap representation to PNG data
            png_data = bitmap_rep.representationUsingType_properties_(NSPNGFileType, None)

            width = bitmap_rep.pixelsWide()
            height = bitmap_rep.pixelsHigh()
            bytes = bitmap_rep.bitsPerPixel() / 8

            cache_dir = os.path.expanduser(f"~/.now-playing/artwork-cache/")
            os.makedirs(cache_dir, exist_ok=True)
            cache_filename = safe_filename(f"{track.databaseID()}_{track.artist()}_{track.album()}_{track.name()}") + ".png"
            cache_filepath = os.path.join(cache_dir, cache_filename)

            logging.debug(f"Artwork: {cache_filepath} ({width}x{height} {bytes} bytes)")

            # send a _copy_ of cache_filepath because writeToFile_atomically_ mutates the string
            png_data.writeToFile_atomically_(copy.copy(cache_filepath), True)

            artwork_paths.append(cache_filepath)


    now_playing_artworks_file = os.path.join(os.path.dirname(__file__), "_data", "apple_now_playing_artworks.txt")
    # Prepare new content
    new_content = "".join(path + "\n" for path in artwork_paths)

    # Read existing content if any
    existing_content = None
    try:
        with open(now_playing_artworks_file, "r") as f:
            existing_content = f.read()
    except FileNotFoundError:
        existing_content = None

    if artwork_paths:
        # Only write if content changed
        if existing_content != new_content:
            with open(now_playing_artworks_file, "w") as f:
                f.write(new_content)
    else:
        # Ensure an empty file exists for consumers
        if existing_content is None:
            open(now_playing_artworks_file, "a").close()

    return artwork_paths

# make a little cache for the image_path so that we
# don't update the image every time we run the script
current_image_path = None

def update_obs_now_playing_image(image_path: str):
    global current_image_path
    import sys
    import time

    import logging
    logging.basicConfig(level=logging.DEBUG)

    if current_image_path and current_image_path == image_path:
        logging.getLogger().debug("Image path is the same as the current image path. Skipping update.")
        return

    sys.path.append('../')
    from obswebsocket import obsws, requests  # noqa: E402

    host = "localhost"
    port = 4455
    password = "tH3NSzMaqHHaWExM"

    ws = obsws(host, port, password)
    ws.connect()

    try:
        ws.call(requests.SetInputSettings(
            inputName="NPImageApple",
            inputSettings={
                "file": image_path,
            }
        ))
        current_image_path = image_path

    except KeyboardInterrupt:
        pass

    ws.disconnect()


def add_song_to_last_5(song):
    # song should return a `track`
    # Connect to the Music app
    music_app = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Music")

    # Check if something is currently playing
    if music_app.isRunning() and music_app.currentTrack() and music_app.currentTrack().name():
        music_app.addSongToRecentlyrm_(song)

    return "Enjoy the silence."

def get_last_5_songs():
    # Connect to the Music app
    music_app = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Music")

    # Check if something is currently playing
    if music_app.isRunning() and music_app.currentTrack() and music_app.currentTrack().name():
        last_five = []
        # TODO implement
    return ""


if __name__ == "__main__":
    # let's parse command line arguments using argparse
    parser = argparse.ArgumentParser(description='Get the current song playing in Apple Music')
    parser.add_argument('--info', action='store_true', help="Get the song info as newline-delimited string.")
    parser.add_argument('--image', action='store_true', help="Get the path to the song cover art.")
    parser.add_argument('--update-obs', action='store_true', help="Update the OBS now playing image.")
    args = parser.parse_args()

    logger = logging.getLogger()

    if args.image:
        # display the album cover
        song_image = get_artworks_for_track()
        if song_image:
            song_image = song_image[0]
        print(song_image)

    elif args.update_obs:
        # update the OBS now playing image
        song_image = get_artworks_for_track()
        if song_image:
            song_image = song_image[0]
            logger.debug("Updating OBS now playing image to the current song's album art: ", song_image)
            update_obs_now_playing_image(song_image)
        else:
            logger.debug("No album art found for the current song.")

    else: # default to current song info
        song_info = get_current_song()
        print(song_info)

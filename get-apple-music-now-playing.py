#!/usr/bin/env python3
import os
import sys
import subprocess


def main() -> int:
    # Delegate to unified CLI: python -m now_playing applemusic [--info|--image|--update-obs]
    args = sys.argv[1:]
    cmd = [sys.executable, "-m", "now_playing", "applemusic"] + args
    env = os.environ.copy()
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
<<<<<<< Current (Your changes)
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
=======
    raise SystemExit(main())
>>>>>>> Incoming (Background Agent changes)

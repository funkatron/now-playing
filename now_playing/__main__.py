import argparse
import logging
import os
from typing import Tuple

from .files import write_artworks_list, write_if_changed
from .obs_client import OBSClient
from .providers import AppleMusicProvider, SpotifyProvider, Provider


def resolve_provider(source: str) -> Tuple[Provider, str, str, str]:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(base_dir, "_data")
    os.makedirs(data_dir, exist_ok=True)

    if source in ("applemusic", "apple", "music"):
        provider = AppleMusicProvider()
        current_song_file = os.path.join(data_dir, "apple_current_song.txt")
        artworks_file = os.path.join(data_dir, "apple_now_playing_artworks.txt")
        obs_source = "NPImageApple"
    elif source in ("spotify", "sp"):
        provider = SpotifyProvider()
        current_song_file = os.path.join(data_dir, "spotify_current_song.txt")
        artworks_file = os.path.join(data_dir, "spotify_now_playing_artworks.txt")
        obs_source = "NPImageSpotify"
    else:
        raise SystemExit(f"Unknown source '{source}'. Use 'applemusic' or 'spotify'.")

    return provider, current_song_file, artworks_file, obs_source


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified Now Playing CLI")
    parser.add_argument("source", nargs="?", default=os.environ.get("NOW_PLAYING_SOURCE", "applemusic"),
                        help="Source: applemusic|spotify (default: env NOW_PLAYING_SOURCE or applemusic)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--info", action="store_true", help="Print 4-line song info and write to file")
    group.add_argument("--image", action="store_true", help="Print path to the first artwork image")
    group.add_argument("--update-obs", action="store_true", help="Update OBS image source to current artwork")
    parser.add_argument("--log-level", default=os.environ.get("PYTHON_LOG_LEVEL", "WARNING"))
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level)

    provider, song_file, artworks_file, obs_source = resolve_provider(args.source)

    if args.image:
        images = provider.get_artworks()
        write_artworks_list(artworks_file, images)
        print(images[0] if images else "")
        return

    if args.update_obs:
        images = provider.get_artworks()
        write_artworks_list(artworks_file, images)
        if images:
            obs = OBSClient()
            logging.getLogger().debug("Updating OBS now playing image: %s", images[0])
            obs.update_image_source(obs_source, images[0])
        else:
            logging.getLogger().debug("No album art found for the current song.")
        return

    # default --info
    info = provider.get_current_song()
    print(info)
    changed = write_if_changed(song_file, info)
    # keep artworks file up-to-date as well
    images = provider.get_artworks()
    write_artworks_list(artworks_file, images)
    if changed:
        logging.getLogger().debug("Updated current song file: %s", song_file)


if __name__ == "__main__":
    main()



#!/usr/bin/env python3
import argparse
import json
from Foundation import NSBundle
from ScriptingBridge import SBApplication

def get_current_song():
    # Get the Spotify application instance
    spotify_app = SBApplication.applicationWithBundleIdentifier_("com.spotify.client")

    # Check if Spotify is running
    if not spotify_app.isRunning():
        return "Spotify is not running."

    # Get the current track
    current_track = spotify_app.currentTrack()
    if current_track is None:
        return "No track is currently playing."

    # From the Spotify applescript documentation:
    # - artist (text, r/o) : The artist of the track.
    # - album (text, r/o) : The album of the track.
    # - disc number (integer, r/o) : The disc number of the track.
    # - duration (integer, r/o) : The length of the track in seconds.
    # - played count (integer, r/o) : The number of times this track has been played.
    # - track number (integer, r/o) : The index of the track in its album.
    # - starred (boolean, r/o) : Is the track starred?
    # - popularity (integer, r/o) : How popular is this track? 0-100
    # - id (text, r/o) : The ID of the item.
    # - name (text, r/o) : The name of the track.
    # - artwork url (text, r/o) : The URL of the track%apos;s album cover.
    # - artwork (image data, r/o) : The property is deprecated and will never be set. Use the 'artwork url' instead.
    # - album artist (text, r/o) : That album artist of the track.
    # - spotify url (text) : The URL of the track.


    # Get the track information
    title = current_track.name()
    artist = current_track.artist()
    album = current_track.album()
    # artwork_url = current_track.artworkUrl()


    # Format the song info
    song_info = f"\"{title}\"\n{artist}\n{album}"

    # now format the current_track as JSON
    song_info = {
        "title": title,
        "artist": artist,
        "album": album
    }

    song_info_str = json.dumps(song_info, indent=4)

    return song_info_str


def get_last_5_songs():
    # Get the Spotify application instance
    spotify_app = SBApplication.applicationWithBundleIdentifier_("com.spotify.client")

    # Check if Spotify is running
    if not spotify_app.isRunning():
        return "Spotify is not running."

    # Get the last 5 tracks
    last_5_tracks = spotify_app.recentTracks()
    if last_5_tracks is None:
        return "No tracks have been played recently."

    # From the Spotify applescript documentation:
    # - artist (text, r/o) : The artist of the track.
    # - album (text, r/o) : The album of the track.
    # - disc number (integer, r/o) : The disc number of the track.
    # - duration (integer, r/o) : The length of the track in seconds.
    # - played count (integer, r/o) : The number of times this track has been played.
    # - track number (integer, r/o) : The index of the track in its album.
    # - starred (boolean, r/o) : Is the track starred?
    # - popularity (integer, r/o) : How popular is this track? 0-100
    # - id (text, r/o) : The ID of the item.
    # - name (text, r/o) : The name of the track.
    # - artwork url (text, r/o) : The URL of the track%apos;s album cover.
    # - artwork (image data, r/o) : The property is deprecated and will never be set. Use the 'artwork url' instead.
    # - album artist (text, r/o) : That album artist of the track.
    # - spotify url (text) : The URL of the track.

    # Get the track information
    last_5_songs = []
    for track in last_5_tracks:
        title = track.name()
        artist = track.artist()
        album = track.album()
        # artwork_url = track.artworkUrl()

        # Format the song info
        song_info = f"\"{title}\"\n{artist}\n{album}"
        last_5_songs.append(song_info)

    return last_5_songs

if __name__ == "__main__":
    # Let's parse command line arguments using argparse
    parser = argparse.ArgumentParser(description='Get the current song playing in Spotify')
    parser.add_argument('-o', '--output', type=str, default='current', help="What to output. Options are: 'current'. Default is 'current'.")
    args = parser.parse_args()

    if args.output == 'current':
        # Get the current song info
        song_info = get_current_song()
        print(song_info)
        last_five = get_last_5_songs()
        print(last_five)
    else:
        print("Invalid output option. Please use 'current'.")
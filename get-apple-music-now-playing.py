#!/usr/bin/env python3

import argparse
import ScriptingBridge

def get_current_song():
    # Connect to the Music app
    music_app = ScriptingBridge.SBApplication.applicationWithBundleIdentifier_("com.apple.Music")
    
    # Check if something is currently playing
    if music_app.isRunning() and music_app.currentTrack() and music_app.currentTrack().name():
        current_track = music_app.currentTrack()
        title = current_track.name()
        artist = current_track.artist()
        album = current_track.album()
        year = current_track.year()
        
        return f"\"{title}\"\n{artist}\n{album}\n{year if year else ''}"

    return "Enjoy the silence."
    

if __name__ == "__main__":
    # let's parse command line arguments using argparse
    parser = argparse.ArgumentParser(description='Get the current song playing in Apple Music')
    parser.add_argument('-o', '--output', type=str, default='current', help="xWhat to output. Ooptions are: 'current'. Default is 'current'.")
    args = parser.parse_args()
    
    if args.output == 'current':
        # get the current song info
        song_info = get_current_song()
        print(song_info)
    else:
        print("Invalid output option. Please use 'current'.")
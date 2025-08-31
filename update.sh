#!/bin/bash

# Unified updater for Apple Music or Spotify.
# Usage: update.sh [applemusic|spotify]
# Or set NOW_PLAYING_SOURCE=applemusic|spotify (arg takes precedence over env).

# get the script's directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATADIR=$DIR/_data
LOGSDIR=$DIR/_logs

# make the required directories if they don't exist
mkdir -p $DATADIR
mkdir -p $LOGSDIR

# source selection (default applemusic)
CLI_SOURCE="$1"
ENV_SOURCE="${NOW_PLAYING_SOURCE:-}"
if [ -n "$CLI_SOURCE" ]; then
    SOURCE="$CLI_SOURCE"
elif [ -n "$ENV_SOURCE" ]; then
    SOURCE="$ENV_SOURCE"
else
    SOURCE="applemusic"
fi

case "$SOURCE" in
  applemusic|apple|music)
    RUN_SCRIPT="get-apple-music-now-playing.py"
    CURRENT_SONG_FILE=$DATADIR/apple_current_song.txt
    CURRENT_SONG_TMP_FILE=$DATADIR/apple_current_song-tmp.txt
    ;;
  spotify|sp)
    RUN_SCRIPT="get-spotify-now-playing.py"
    CURRENT_SONG_FILE=$DATADIR/spotify_current_song.txt
    CURRENT_SONG_TMP_FILE=$DATADIR/spotify_current_song-tmp.txt
    ;;
  *)
    echo "Unknown source '$SOURCE'. Use 'applemusic' or 'spotify'." >&2
    exit 1
    ;;
esac

# define log prefix
CURRENT_DATETIME=$(date +"%Y%m%d_%H%M%S")
CURRENT_DATE=$(date +"%Y-%m-%d")
LOG_PREFIX="[$(basename $0) $CURRENT_DATETIME][$SOURCE]"

# log any output to a file: _logs/<script-name>_<date-started>.log
exec > >(tee -a "$LOGSDIR/$(basename "$0")_$CURRENT_DATE.log") 2>&1

# set python log level to "debug"
export PYTHON_LOG_LEVEL=DEBUG;

echo "$LOG_PREFIX Running $RUN_SCRIPT to get current song info.";
COMMAND="$DIR/venv/bin/python $DIR/$RUN_SCRIPT --info"
echo "$LOG_PREFIX Running command: $COMMAND > $CURRENT_SONG_TMP_FILE"
$COMMAND > $CURRENT_SONG_TMP_FILE

if [ -s $CURRENT_SONG_TMP_FILE ]; then
    if cmp -s $CURRENT_SONG_TMP_FILE $CURRENT_SONG_FILE; then
        rm -f $CURRENT_SONG_TMP_FILE
        # update OBS image for the selected source
        if [ "$SOURCE" = "spotify" ] || [ "$SOURCE" = "sp" ]; then
            $DIR/venv/bin/python $DIR/get-spotify-now-playing.py --update-obs
        else
            $DIR/venv/bin/python $DIR/get-apple-music-now-playing.py --update-obs
        fi
    else
        mv $CURRENT_SONG_TMP_FILE $CURRENT_SONG_FILE
        echo "$LOG_PREFIX Updated current song: $(cat $CURRENT_SONG_FILE)"
        if [ "$SOURCE" = "spotify" ] || [ "$SOURCE" = "sp" ]; then
            $DIR/venv/bin/python $DIR/get-spotify-now-playing.py --update-obs
        else
            $DIR/venv/bin/python $DIR/get-apple-music-now-playing.py --update-obs
        fi
    fi
else
    touch $CURRENT_SONG_FILE
fi
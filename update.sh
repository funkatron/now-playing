#!/bin/bash

# This script retrieves the current song playing on Apple Music, and writes it to a file.
# It is intended to be run as a cron job every minute, and will only write to the file if the song has changed.
# The script also logs its output to a file in the _logs directory.

# get the script's directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATADIR=$DIR/_data
LOGSDIR=$DIR/_logs

# make the required directories if they don't exist
mkdir -p $DATADIR
mkdir -p $LOGSDIR

# define the file paths for the current song
CURRENT_DATETIME=$(date +"%Y%m%d_%H%M%S")
CURRENT_DATE=$(date +"%Y-%m-%d")
LOG_PREFIX="[$(basename $0) $CURRENT_DATETIME]"

CURRENT_SONG_FILE=$DATADIR/current_song.txt
CURRENT_SONG_TMP_FILE=$DATADIR/current_song-tmp.txt
CURRENT_SONG_DATED_FILE=$DATADIR/played_song-$CURRENT_DATETIME.txt

# log any output to a file: _logs/<script-name>_<date-started>.log
exec > >(tee -a "$LOGSDIR/$(basename "$0")_$CURRENT_DATE.log") 2>&1

# set python log level to "debug"
export PYTHON_LOG_LEVEL=DEBUG;
# run the python script using the venv interpreter to get the current song, and write it to a tmp file
$DIR/venv/bin/python $DIR/get-apple-music-now-playing.py --info > $CURRENT_SONG_TMP_FILE

# if the tmp file is not empty, move it to current_song.txt
if [ -s $CURRENT_SONG_TMP_FILE ]; then
    # if the contents of the tmp file are identical to the current_song.txt, just remove the tmp file.
    if cmp -s $CURRENT_SONG_TMP_FILE $CURRENT_SONG_FILE; then
        rm $CURRENT_SONG_TMP_FILE
        echo "$LOG_PREFIX No change in current song; skipping update."
        $DIR/venv/bin/python $DIR/get-apple-music-now-playing.py --update-obs

    else
        # move the tmp file to current_song.txt
        mv $CURRENT_SONG_TMP_FILE $CURRENT_SONG_FILE
        echo "$LOG_PREFIX Updated current song: $(cat $CURRENT_SONG_FILE)"
        # update the now playing image
        $DIR/venv/bin/python $DIR/get-apple-music-now-playing.py --update-obs
    fi
fi
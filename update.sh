# outputs the currently playing song to a file in the data directory

# get the script's directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATADIR=$DIR/_data
LOGSDIR=$DIR/_logs

# make the required directories if they don't exist
mkdir -p $DATADIR
mkdir -p $LOGSDIR

# log any output to a file: _logs/<script-name>_<date-started>.log
exec &> $DIR/_logs/update_$(date +"%Y-%m-%d").log

# copy the previous current_song.txt to current_song-<creation_datetime>.txt, if it exists
[ -f $DATADIR/current_song.txt ] && cp $DATADIR/current_song.txt $DATADIR/current_song-$(date +"%Y%m%d_%H%M%S").txt

# run the python script using the venv interpreter to get the current song, and write it to a tmp file
$DIR/venv/bin/python $DIR/get-apple-music-now-playing.py > $DATADIR/current_song-tmp.txt


# if the tmp file is not empty, move it to current_song.txt
if [ -s $DATADIR/current_song-tmp.txt ]; then
    # if the contents of the tmp file are identical to the current_song.txt, just remove the tmp file.
    if cmp -s $DATADIR/current_song-tmp.txt $DATADIR/current_song.txt; then
        rm $DATADIR/current_song-tmp.txt
        echo "No change in current song; skipping update."
    else
        mv $DATADIR/current_song-tmp.txt $DATADIR/current_song.txt
        echo "Updated current song."
    fi
fi

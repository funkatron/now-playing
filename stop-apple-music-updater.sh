# look up the process id of the Apple Music updater and kill it.

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

PID_FILE="$DIR/apple-music-updater.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No Apple Music updater PID file found."
    exit 0
fi

# get the PID
PID=$(cat "$PID_FILE")

# kill the process
kill $PID 2>/dev/null || true

# remove the PID file
rm -f "$PID_FILE"

# report that we're done
echo "Apple Music updater stopped with PID $PID."



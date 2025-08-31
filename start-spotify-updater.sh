# This script is run at startup to start the Spotify updater in the background.

# make this overridable by setting the environment variable, or if it is passed
# as an argument to the script, but otherwise default to 5 seconds;.
INTERVAL_SECONDS=${INTERVAL_SECONDS:-5}

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PID_FILE="$DIR/spotify-updater.pid"

function run_updater {
    # report that we are starting and what the interval is
    echo "Starting $DIR/update-spotify.sh with interval of $INTERVAL_SECONDS seconds..."
    while true; do
        $DIR/update-spotify.sh
        sleep $INTERVAL_SECONDS
    done
}

# is there already a PID file? If so, ask the user if they want to kill the process and start a new one.
if [ -f "$PID_FILE" ]; then
    echo "There is already a Spotify updater running with PID $(cat "$PID_FILE")."
    read -p "Do you want to kill it and start a new one? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping the old Spotify updater..."
        OLD_PID=$(cat "$PID_FILE")
        kill $OLD_PID 2>/dev/null || true
        rm -f "$PID_FILE"
    else
        echo "Not starting a new Spotify updater. Exiting."
        exit 0
    fi
fi

## report what we're doing
echo "Starting Spotify updater..."

# run the updater function in the background and get the PID so we can print it out
run_updater &

# print the PID
echo $! > "$PID_FILE"

# report that we're done
echo "Spotify updater started in the background with PID $!"



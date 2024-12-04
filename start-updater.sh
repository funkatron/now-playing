# This script is run at startup to start the updater in the background.

# make this overridable by setting the environment variable, or if it is passed
# as an argument to the script, but otherwise default to 5 seconds;.
INTERVAL_SECONDS=${INTERVAL_SECONDS:-5}

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

function run_updater {
    # report that we are starting and what the interval is
    echo "Starting $DIR/update.sh with interval of $INTERVAL_SECONDS seconds..."
    while true; do
        $DIR/update.sh
        sleep $INTERVAL_SECONDS
    done
}

# is there already a PID file? If so, we should ask the user if they want to kill the process and start a new one.
if [ -f $DIR/updater.pid ]; then
    echo "There is already an updater running with PID $(cat $DIR/updater.pid)."
    read -p "Do you want to kill it and start a new one? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping the old updater..."
        ./stop-updater.sh
    else
        echo "Not starting a new updater. Exiting."
        exit 0
    fi
fi

## report what we're doing
echo "Starting updater..."

# run the updater function in the background and get the PID so we can print it out
run_updater &

# print the PID
echo $! > $DIR/updater.pid

# report that we're done
echo "Updater started in the background with PID $!"

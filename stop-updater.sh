# look up the process id of the stop-updater.sh script and kill it.

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# process ID is stored in the updater.pid file in the same directory as the stop-updater.sh script

# get the PID
PID=$(cat $DIR/updater.pid)

# kill the process
kill $PID

# remove the PID file
rm $DIR/updater.pid

# report that we're done
echo "Updater stopped with PID $PID."

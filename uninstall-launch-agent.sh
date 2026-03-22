#!/bin/bash

set -euo pipefail

LABEL="${NOW_PLAYING_LAUNCHD_LABEL:-com.funkatron.now-playing}"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"

echo "Stopped and removed LaunchAgent: $LABEL"

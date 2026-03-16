#!/bin/bash

set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LABEL="${NOW_PLAYING_LAUNCHD_LABEL:-com.funkatron.now-playing}"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/$LABEL.plist"

if [ -f "$DIR/config.env" ]; then
  set -a
  source "$DIR/config.env"
  set +a
fi

HOST="${NOW_PLAYING_HOST:-127.0.0.1}"
PORT="${NOW_PLAYING_PORT:-8976}"

mkdir -p "$PLIST_DIR" "$DIR/_logs" "$DIR/_data"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>WorkingDirectory</key>
  <string>$DIR</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DIR/run-daemon.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$DIR/_logs/launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$DIR/_logs/launchd.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl enable "gui/$(id -u)/$LABEL"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo "Installed and started LaunchAgent: $LABEL"
echo "HTTP API: http://$HOST:$PORT/current"

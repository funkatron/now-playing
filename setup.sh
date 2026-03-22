#!/bin/bash

set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$DIR/.venv"

if command -v uv >/dev/null 2>&1; then
  uv sync --project "$DIR"
else
  if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
  fi

  "$VENV_DIR/bin/pip" install -r "$DIR/requirements.txt"
fi
chmod +x "$DIR"/*.py "$DIR"/*.sh

if [ ! -f "$DIR/config.env" ]; then
  cp "$DIR/config.env.example" "$DIR/config.env"
  echo "Created $DIR/config.env"
fi

mkdir -p "$DIR/_data" "$DIR/_logs"

echo
echo "Setup complete."
echo
echo "Next steps:"
echo "1. Edit $DIR/config.env if you want Spotify-only or OBS websocket settings."
echo "2. Start the background service with: uv run np install-service"
echo "3. Check current state at: http://127.0.0.1:8976/current"

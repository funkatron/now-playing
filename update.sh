#!/bin/bash

set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
mkdir -p "$DIR/_logs"
CURRENT_DATE=$(date +"%Y-%m-%d")
exec > >(tee -a "$DIR/_logs/update_$CURRENT_DATE.log") 2>&1

echo "[$(basename "$0")] Syncing current track state..."
if command -v uv >/dev/null 2>&1; then
  exec uv run --project "$DIR" python "$DIR/np_service.py" sync
fi

PYTHON_BIN="${PYTHON_BIN:-$DIR/.venv/bin/python}"
exec "$PYTHON_BIN" "$DIR/np_service.py" sync

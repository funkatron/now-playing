#!/bin/bash

set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ -f "$DIR/config.env" ]; then
  set -a
  source "$DIR/config.env"
  set +a
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run --project "$DIR" python "$DIR/np_service.py" serve
fi

PYTHON_BIN="${PYTHON_BIN:-$DIR/.venv/bin/python}"

exec "$PYTHON_BIN" "$DIR/np_service.py" serve

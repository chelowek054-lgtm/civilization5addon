#!/usr/bin/env bash
# Full analysis window: advisor, metric tree, history of saved games.
# Uses the project's .venv when it exists (create it with ./setup.sh).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=python3
[ -x "$SCRIPT_DIR/.venv/bin/python" ] && PY="$SCRIPT_DIR/.venv/bin/python"
exec "$PY" "$SCRIPT_DIR/viewer/civstats.py" "$@"

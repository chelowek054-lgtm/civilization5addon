#!/usr/bin/env bash
# Civ 5 stats window: advisor, graphs, metric tree, cheat check, saved games.
# Optional argument: a saved game from saves/.
# Uses the project's .venv when it exists (create it with ./setup.sh).
# Set CIVSTATS_LOG=/path/to/Lua.log if the log is not found automatically.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=python3
[ -x "$SCRIPT_DIR/.venv/bin/python" ] && PY="$SCRIPT_DIR/.venv/bin/python"
exec "$PY" "$SCRIPT_DIR/viewer/civstats.py" "$@"

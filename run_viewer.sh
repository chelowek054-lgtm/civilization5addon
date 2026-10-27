#!/usr/bin/env bash
# Starts the Civ 5 stats viewer. Optional argument: a saved game from saves/.
# Set CIVSTATS_LOG=/path/to/Lua.log if the log is not found automatically.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/viewer/civstats.py" "$@"

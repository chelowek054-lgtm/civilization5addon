#!/usr/bin/env bash
# Starts the compact Civ 5 stats overlay. Optional argument: a saved game from saves/.
# The + button or a click on a metric opens the full analysis window (run_analysis.sh).
# Set CIVSTATS_LOG=/path/to/Lua.log if the log is not found automatically.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/viewer/overlay.py" "$@"

#!/usr/bin/env bash
# Full analysis window: advisor, metric tree, history of saved games.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/viewer/civstats.py" "$@"

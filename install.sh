#!/usr/bin/env bash
# Installs the in-game logger into Civ 5 on Linux (native Aspyr port or Proton)
# and turns on Lua logging. Run again after game updates.
#
#   ./install.sh                        auto-detect
#   ./install.sh --game-dir DIR         Civ 5 install folder
#   ./install.sh --user-dir DIR         folder with config.ini and Logs/
#   ./install.sh --uninstall            restore original files
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAME_DIR=""
USER_DIR=""
UNINSTALL=0

while [ $# -gt 0 ]; do
    case "$1" in
        --game-dir) GAME_DIR="$2"; shift 2 ;;
        --user-dir) USER_DIR="$2"; shift 2 ;;
        --uninstall) UNINSTALL=1; shift ;;
        -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

GAME_NAME="Sid Meier's Civilization V"
if [ -z "$GAME_DIR" ]; then
    for lib in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.steam/root" \
               "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        if [ -d "$lib/steamapps/common/$GAME_NAME" ]; then
            GAME_DIR="$lib/steamapps/common/$GAME_NAME"
            break
        fi
    done
fi
if [ -z "$GAME_DIR" ] || [ ! -d "$GAME_DIR" ]; then
    echo "Civilization V not found. Pass it with --game-dir \"/path/to/$GAME_NAME\"" >&2
    exit 1
fi

# The native port uses lower-case asset paths, Proton the Windows ones: search case-insensitively.
IN_GAME_XML="$(find "$GAME_DIR" -ipath '*dlc/expansion2/ui/ingame/ingame.xml' -print -quit)"
if [ -z "$IN_GAME_XML" ]; then
    echo "Brave New World UI (DLC/Expansion2/UI/InGame/InGame.xml) not found in $GAME_DIR" >&2
    exit 1
fi
UI_DIR="$(dirname "$IN_GAME_XML")"
BACKUP="$IN_GAME_XML.civstats-backup"

if [ "$UNINSTALL" = 1 ]; then
    [ -f "$BACKUP" ] && mv -f "$BACKUP" "$IN_GAME_XML"
    rm -f "$UI_DIR/CivStatsLogger.lua" "$UI_DIR/CivStatsLogger.xml"
    echo "Uninstalled."
    exit 0
fi

cp -f "$SCRIPT_DIR/game/UI/CivStatsLogger.lua" "$SCRIPT_DIR/game/UI/CivStatsLogger.xml" "$UI_DIR/"
[ -f "$BACKUP" ] || cp "$IN_GAME_XML" "$BACKUP"

# Copy of the original InGame.xml with our hidden context before the last </Context>
python3 - "$BACKUP" "$IN_GAME_XML" <<'EOF'
import sys
src, dst = sys.argv[1:3]
xml = open(src, encoding="utf-8-sig").read()
i = xml.rindex("</Context>")
line = '\t<LuaContext FileName="CivStatsLogger" ID="CivStatsLogger" Hidden="1"/>\n'
open(dst, "w", encoding="utf-8").write(xml[:i] + line + xml[i:])
EOF

# Enable Lua.log in config.ini
if [ -z "$USER_DIR" ]; then
    for d in "$HOME/.local/share/Aspyr/Sid Meier's Civilization 5" \
             "$(dirname "$(dirname "$GAME_DIR")")/compatdata/8930/pfx/drive_c/users/steamuser/Documents/My Games/Sid Meier's Civilization 5"; do
        if [ -f "$d/config.ini" ]; then USER_DIR="$d"; break; fi
    done
fi
if [ -n "$USER_DIR" ] && [ -f "$USER_DIR/config.ini" ]; then
    sed -i 's/LoggingEnabled[[:space:]]*=[[:space:]]*0/LoggingEnabled = 1/' "$USER_DIR/config.ini"
    echo "Logging enabled in $USER_DIR/config.ini"
else
    echo "config.ini not found (start the game once, then re-run, or pass --user-dir)." >&2
    echo "You can also set LoggingEnabled = 1 in config.ini by hand." >&2
fi
echo "Installed into $UI_DIR"

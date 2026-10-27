# Civ 5 Stats

Live graphs and strategy analysis for **Sid Meier's Civilization V: Brave New World**.

A small in-game logger writes ~90 stats for every major civilization each turn to
`Lua.log`; a desktop viewer reads that log and draws the graphs in a separate
window that can stay on top of the game.

The logger only *reads* game state, so it is safe in **multiplayer**: no desyncs,
and other players don't need to install it.

## Features

- **Metric tree** — all stats are normalized to a 0–100 index (0 = worst civ, 100 = best)
  and grouped: *Overall strength → 8 groups (scale, economy, science, culture,
  faith, stability, military, score) → subgroups → raw stats*. Select any node to
  see it per turn for every civ, plus what your own index is made of.
- **Dashboard**, single-metric graphs and a summary table.
- **Overlay mode** — always on top, adjustable transparency, compact side panel.
- **Automatic game archive** — every game is saved to `saves/` while the viewer runs.
- **Game history** — pick any saved game from the *Игра* (Game) list to analyse it; the current game keeps being recorded in the background.
- Civs you haven't met are hidden by default.

## Requirements

- Windows, Civilization V with **Brave New World**
- Python 3.10+ with `matplotlib` (`tkinter` ships with the standard Windows installer)

```bash
pip install matplotlib
```

## Installation

1. Install the logger into the game and enable Lua logging:

   ```bash
   powershell -ExecutionPolicy Bypass -File install.ps1
   ```

   If the game is not in the default location, pass it explicitly:

   ```bash
   powershell -ExecutionPolicy Bypass -File install.ps1 -GameDir "C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization V"
   ```

   The script:
   - copies `CivStatsLogger.lua/.xml` into `Assets\DLC\Expansion2\UI\InGame`;
   - adds one `<LuaContext>` line to that folder's `InGame.xml` (the original is kept
     as `InGame.xml.civstats-backup`);
   - sets `LoggingEnabled = 1` in `Documents\My Games\Sid Meier's Civilization 5\config.ini`.

2. **Fully restart** Civilization V and start or load a game.
3. Run the viewer: double-click `run_viewer.bat`.

To see the game behind the overlay, run Civ 5 in **windowed / borderless** mode;
exclusive fullscreen draws over every other window.

### Uninstall

```bash
powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall
```

### After a game update

Steam updates or "Verify integrity of game files" restore the original `InGame.xml`.
Run `install.ps1` again.

## Viewing a recorded game

Choose it in the *Игра* (Game) drop-down at the top of the window (newest first, `▶ Текущая игра` is the live game). You can also drag a file from `saves/` onto `run_viewer.bat`, or:

```bash
python viewer/civstats.py saves/<file>.log
```

## Project layout

| Path | What |
|---|---|
| `game/UI/CivStatsLogger.lua` | In-game logger (one `CIVSTATS|…` line per civ per turn) |
| `viewer/civstats.py` | Viewer window, log reader, game archive |
| `viewer/metrics_tree.py` | Metric tree and index calculation |
| `install.ps1` | Installer / uninstaller |

## Notes

- If a stat's API method doesn't exist in your game version it logs `0` and is
  left out of the indices.
- The logger can technically read rivals' data that the normal UI hides; the
  viewer shows only civs you have met unless you tick the checkbox.

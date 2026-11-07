"""Background archiver: copies every Civ 5 game from Lua.log into saves/.

Runs without a window, so games are saved even when the overlay and the
analysis window are closed. The game recreates Lua.log on every launch (and
after a crash), so whatever is not copied while the game runs is lost.
install.ps1 starts it at logon; the overlay and the analysis window start it
too. A second copy exits at once.

    python viewer/archiver.py
"""
import os
import time

from civstats import ARCHIVE_DIR, LOG_PATH, Data, try_lock

POLL_S = 2


def main():
    me = try_lock(os.path.join(ARCHIVE_DIR, ".archiver.lock"))
    if me is None:
        return  # already running
    data = Data(LOG_PATH)
    while True:
        data.poll()
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()

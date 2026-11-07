"""Cheat check from the command line; the logic lives in viewer/cheats.py.

    python tools/cheat_check.py [saves/<file>.log] [--all] [--me]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viewer"))
import cheats  # noqa: E402

cheats.main()

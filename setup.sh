#!/usr/bin/env bash
# Creates .venv in the project folder and installs the Python dependencies.
# tkinter comes from the system (python3-tk / python3-tkinter / tk).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
echo "Done. Start the overlay with ./start.sh"

@echo off
rem Compact overlay; the + button or a click on a metric opens the full analysis window.
start "" pythonw "%~dp0viewer\overlay.py" %*

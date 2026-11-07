@echo off
rem Civ 5 stats window: advisor, graphs, metric tree, cheat check, saved games.
rem Optional argument: a saved game from saves\. Uses the project's .venv when it exists (setup.bat).
set "PY=pythonw"
if exist "%~dp0.venv\Scripts\pythonw.exe" set "PY=%~dp0.venv\Scripts\pythonw.exe"
start "" "%PY%" "%~dp0viewer\civstats.py" %*

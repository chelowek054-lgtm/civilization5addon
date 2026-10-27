@echo off
rem Full analysis window: advisor, metric tree, history of saved games.
rem Uses the project's .venv when it exists (create it with setup.bat).
set "PY=pythonw"
if exist "%~dp0.venv\Scripts\pythonw.exe" set "PY=%~dp0.venv\Scripts\pythonw.exe"
start "" "%PY%" "%~dp0viewer\civstats.py" %*

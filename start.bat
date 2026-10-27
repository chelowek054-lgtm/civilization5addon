@echo off
rem Compact overlay; the + button or a click on a metric opens the full analysis window.
rem Uses the project's .venv when it exists (create it with setup.bat).
set "PY=pythonw"
if exist "%~dp0.venv\Scripts\pythonw.exe" set "PY=%~dp0.venv\Scripts\pythonw.exe"
start "" "%PY%" "%~dp0viewer\overlay.py" %*

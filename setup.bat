@echo off
rem Creates .venv in the project folder and installs the Python dependencies.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe python -m venv .venv || goto :error
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
echo.
echo Done. Start the overlay with start.bat
exit /b 0
:error
echo Setup failed. Is Python 3.10+ installed and on PATH?
exit /b 1

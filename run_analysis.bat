@echo off
rem Full analysis window: advisor, metric tree, history of saved games.
start "" pythonw "%~dp0viewer\civstats.py" %*

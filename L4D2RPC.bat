@echo off
rem L4D2 Better Presence - runs with a console showing the log. Ctrl+C or closing the window clears the card.
title L4D2 Better Presence
cd /d "%~dp0"
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  echo Python was not found. Install Python 3.10+ from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during the installation.
  pause
  exit /b 1
)
%PY% -m l4d2_rpc %*
if errorlevel 1 pause

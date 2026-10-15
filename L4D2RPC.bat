@echo off
rem L4D2 Better Presence with a console showing what it sends. Ctrl+C or closing the window clears the card.
rem Options: --dry-run, --simulate, --dump, -v (see README > Tools).
title L4D2 Better Presence
cd /d "%~dp0"
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  echo Python is not installed ^(or not in PATH^).
  echo Install Python 3.10 or newer from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" at the start of the installer. Then run this file again.
  echo.
  choice /m "Open the Python download page now"
  if not errorlevel 2 start "" https://www.python.org/downloads/
  pause
  exit /b 1
)
%PY% -m l4d2_rpc %*
if errorlevel 1 pause

@echo off
rem Stops starting L4D2 Better Presence with Windows (removes the Startup shortcut).
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
%PY% -m l4d2_rpc startup off
pause

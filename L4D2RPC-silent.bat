@echo off
rem L4D2 Better Presence without a window (pythonw). Stop it from the Task Manager (pythonw.exe) or log off.
cd /d "%~dp0"
set "PYW="
where pythonw >nul 2>nul && set "PYW=pythonw"
if not defined PYW where pyw >nul 2>nul && set "PYW=pyw -3"
if not defined PYW (
  echo pythonw was not found. Install Python 3.10+ from https://www.python.org/downloads/
  pause
  exit /b 1
)
start "" %PYW% -m l4d2_rpc

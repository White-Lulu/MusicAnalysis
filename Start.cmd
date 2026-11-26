@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup.ps1 first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -B launch.py
if errorlevel 1 pause

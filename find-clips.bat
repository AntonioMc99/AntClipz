@echo off
REM Double-click this file to run the Phase 1 clip finder.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setup has not been run yet. Run setup.ps1 first - see README.md
  pause
  exit /b 1
)
".venv\Scripts\python.exe" find_clips.py
echo.
pause

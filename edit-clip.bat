@echo off
REM Double-click to edit the #1 clip, or run:  edit-clip.bat 3
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setup has not been run yet. Run setup.ps1 first - see README.md
  pause
  exit /b 1
)
".venv\Scripts\python.exe" edit_clip.py %1
echo.
pause

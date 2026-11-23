@echo off
REM Double-click to download the #1 clip, or run:  download-clip.bat 3
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setup has not been run yet. Run setup.ps1 first - see README.md
  pause
  exit /b 1
)
".venv\Scripts\python.exe" download_clip.py %1
echo.
pause

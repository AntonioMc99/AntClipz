@echo off
REM Double-click to send the #1 edited clip to your review folder, or run:  send-to-review.bat 3
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setup has not been run yet. Run setup.ps1 first - see README.md
  pause
  exit /b 1
)
".venv\Scripts\python.exe" send_to_review.py %1
echo.
pause

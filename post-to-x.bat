@echo off
REM Posts clips from "2 - approved" to X. Asks you to type YES before each post.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setup has not been run yet. Run setup.ps1 first - see README.md
  pause
  exit /b 1
)
".venv\Scripts\python.exe" post_to_x.py
echo.
pause

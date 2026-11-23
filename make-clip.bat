@echo off
REM One step: download + edit + send to review.  make-clip.bat (clip #1) or  make-clip.bat 3
REM Run find-clips.bat first to get a fresh list of clips.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setup has not been run yet. Run setup.ps1 first - see README.md
  pause
  exit /b 1
)
set RANK=%1
if "%RANK%"=="" set RANK=1
echo ===== Downloading clip #%RANK% =====
".venv\Scripts\python.exe" download_clip.py %RANK% || goto failed
echo.
echo ===== Editing clip #%RANK% =====
".venv\Scripts\python.exe" edit_clip.py %RANK% || goto failed
echo.
echo ===== Sending clip #%RANK% to review =====
".venv\Scripts\python.exe" send_to_review.py %RANK% || goto failed
echo.
pause
exit /b 0
:failed
echo.
echo Stopped because of the error above.
pause
exit /b 1

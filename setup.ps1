# One-time setup for AntClipz on Windows.
# Run from the AntClipz folder with:
#   powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== AntClipz setup ==" -ForegroundColor Cyan

# 1. Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python -or $python.Source -like "*WindowsApps*") {
    Write-Host "Python not found. Installing Python 3.12 with winget..." -ForegroundColor Yellow
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    Write-Host ""
    Write-Host "Python installed. CLOSE this window, open a NEW PowerShell window, and run setup again." -ForegroundColor Green
    exit 0
}
Write-Host "Found $(python --version)"

# 2. Virtual environment (private library folder, like node_modules)
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment in .venv ..."
    python -m venv .venv
}

# 3. Libraries
Write-Host "Installing libraries..."
& ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet

# 4. Secrets file
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "Opening .env in Notepad. Paste your Twitch Client ID and NEW Client Secret" -ForegroundColor Yellow
    Write-Host "after the = signs (no spaces, no quotes), then Save and close Notepad." -ForegroundColor Yellow
    Start-Process notepad ".env" -Wait
}

Write-Host ""
Write-Host "Setup done! Double-click find-clips.bat to find clips." -ForegroundColor Green

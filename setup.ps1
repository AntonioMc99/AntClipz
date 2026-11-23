# One-time setup for AntClipz on Windows.
# Run from the AntClipz folder with:
#   powershell -ExecutionPolicy Bypass -File setup.ps1

Set-Location $PSScriptRoot
Write-Host "== AntClipz setup ==" -ForegroundColor Cyan

function Stop-WithError($message) {
    Write-Host ""
    Write-Host "ERROR: $message" -ForegroundColor Red
    exit 1
}

# Find a real python.exe. Windows often has a fake "python" (a Microsoft Store
# shortcut) on the PATH, and winget installs don't always update the PATH,
# so we look in several places and use the full path to python.exe.
function Find-Python {
    $candidates = @()

    # 1. The "py" launcher that comes with Python from python.org / winget
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            $exe = & py -3 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { $candidates += $exe.Trim() }
        } catch { }
    }

    # 2. Usual install folders
    $candidates += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | ForEach-Object { $_.FullName }

    # 3. Whatever "python" is on the PATH, unless it's the Store shortcut
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") { $candidates += $cmd.Source }

    return $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

# 1. Python
$pythonExe = Find-Python
if (-not $pythonExe) {
    Write-Host "Python not found. Installing Python 3.12 with winget..." -ForegroundColor Yellow
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $pythonExe = Find-Python
    if (-not $pythonExe) {
        Stop-WithError "Python still not found after installing. Close this window, open a new PowerShell window in this folder, and run setup again."
    }
}
Write-Host "Using Python: $pythonExe"
& $pythonExe --version

# 2. Virtual environment (private library folder, like node_modules)
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment in .venv ..."
    & $pythonExe -m venv .venv
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Could not create the virtual environment." }
}

# 3. Libraries
Write-Host "Installing libraries (this can take a minute)..."
& ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet --disable-pip-version-check
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Stop-WithError "Installing libraries failed. Copy the messages above and send them to Claude." }

# 4. Secrets file
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "Opening .env in Notepad. Paste your Twitch Client ID and NEW Client Secret" -ForegroundColor Yellow
    Write-Host "after the = signs (no spaces, no quotes), then Save and close Notepad." -ForegroundColor Yellow
    Start-Process notepad ".env" -Wait
}

Write-Host ""
Write-Host "Setup done! Now run:  .\find-clips.bat" -ForegroundColor Green

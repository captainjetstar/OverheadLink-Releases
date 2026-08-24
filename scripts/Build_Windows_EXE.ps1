$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.12 -m venv .venv
}

& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -r requirements.txt "pyinstaller>=6.10,<7"
& .venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name OverheadLink `
    --add-data "profiles;profiles" `
    run_overheadlink.py

Write-Host "Built: $ProjectRoot\dist\OverheadLink\OverheadLink.exe"


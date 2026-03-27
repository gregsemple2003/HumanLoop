Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$desktopExe = Join-Path $projectRoot ".venv\Scripts\humanloop-desktop.exe"

if (-not (Test-Path $desktopExe)) {
    throw "HumanLoop desktop launcher was not found at $desktopExe. Install desktop dependencies first with '.\.venv\Scripts\python.exe -m pip install -e .[desktop]'."
}

$process = Start-Process -FilePath $desktopExe -WorkingDirectory $projectRoot -PassThru

Write-Host "Started HumanLoop Desktop."
Write-Host "  pid: $($process.Id)"
Write-Host "  exe: $desktopExe"

<# :
@echo off
start "Image Processing Toolbox" pwsh -NoProfile -ExecutionPolicy Bypass -Command "& { $dir = '%~dp0'; . ([ScriptBlock]::Create((Get-Content -Raw '%~f0'))) }"
exit /b
#>
$ErrorActionPreference = "Stop"
Set-Location $dir

Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "  Python not found. Please install Python 3.10+ first:"
    Write-Host "  https://www.python.org/downloads/"
    Write-Host ""
    Read-Host "Press Enter"
    exit 1
}

python main.py
if ($LASTEXITCODE -ne 0) { Read-Host "Press Enter" }

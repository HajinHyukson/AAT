# Daily KOSPI pilot refresh, intended for Windows Task Scheduler.
# Imports new Acquin rows, promotes them, runs attribution for new windows,
# and refreshes dashboard summaries. Logs to logs\pilot_kospi_daily_<date>.log.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$logDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}
$logFile = Join-Path $logDir ("pilot_kospi_daily_{0}.log" -f (Get-Date -Format "yyyyMMdd"))

function Write-Log([string]$message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

Write-Log "starting pilot KOSPI daily refresh"

try {
    docker compose up -d postgres | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose up failed; is Docker Desktop running?"
    }

    $env:DATABASE_URL = "postgresql+psycopg://attribution:attribution@localhost:55432/aat_pilot_kospi"
    $python = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw ".venv not found; run SETUP.md local Python steps first"
    }

    # Native stderr lines (e.g. the continuity-suspect WARNING) must not become
    # terminating errors under Stop preference, and must land in the log as utf8.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $python -m jobs.run_pilot_kospi_daily 2>&1 |
        ForEach-Object { $_.ToString() } |
        Add-Content -Path $logFile -Encoding utf8
    $ErrorActionPreference = $previousPreference
    if ($LASTEXITCODE -ne 0) {
        throw "jobs.run_pilot_kospi_daily exited with code $LASTEXITCODE"
    }
    Write-Log "completed pilot KOSPI daily refresh"
    exit 0
}
catch {
    Write-Log "FAILED: $_"
    exit 1
}

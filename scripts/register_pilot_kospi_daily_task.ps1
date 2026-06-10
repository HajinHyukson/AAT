# Registers (or replaces) the Windows scheduled task that runs the daily
# KOSPI pilot refresh at 17:30 local time, after the Acquin database has
# written its post-close rows (~16:22 KST).
#
# Remove with:
#   Unregister-ScheduledTask -TaskName "AAT Pilot KOSPI Daily" -Confirm:$false

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $repoRoot "scripts\run_pilot_kospi_daily.ps1"
$taskName = "AAT Pilot KOSPI Daily"

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At "17:30"
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "AAT: import Acquin KOSPI data, promote, run attribution, refresh dashboard summaries." `
    -Force | Out-Null

Write-Host "Registered scheduled task '$taskName' (daily 17:30, runs $runner)."

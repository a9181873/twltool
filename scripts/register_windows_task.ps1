param(
    [string]$TaskName = "TaiwanLifeWebsiteMonitor",
    [string]$RepoRoot = "",
    [string]$StartTime = "08:00",
    [int]$HoursInterval = 12,
    [switch]$EnableRpa84,
    [switch]$RunWatchdogBefore
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$wrapper = Join-Path $RepoRoot "scripts\run_taiwanlife_monitor.ps1"
if (-not (Test-Path $wrapper)) {
    throw "找不到 wrapper：$wrapper"
}

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$wrapper`"",
    "-RepoRoot", "`"$RepoRoot`""
)

if ($EnableRpa84) {
    $arguments += "-EnableRpa84"
}
if ($RunWatchdogBefore) {
    $arguments += "-RunWatchdogBefore"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($arguments -join " ")
$startParts = $StartTime.Split(":")
$firstRun = [datetime]::Today.AddHours([int]$startParts[0]).AddMinutes([int]$startParts[1])
if ($firstRun -lt (Get-Date)) {
    $firstRun = $firstRun.AddDays(1)
}
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At $firstRun `
    -RepetitionInterval (New-TimeSpan -Hours $HoursInterval) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "台灣人壽官網巡檢排程" `
    -Force | Out-Null

Write-Output "已建立或更新排程：$TaskName"

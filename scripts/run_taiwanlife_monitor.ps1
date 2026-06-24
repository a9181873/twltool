param(
    [string]$RepoRoot = "",
    [string]$Python = "",
    [string]$Config = "config\taiwanlife.json",
    [string]$OutputDir = "reports",
    [string]$Scheduler = "windows-task-scheduler",
    [string]$PowerAutomateWebhookUrl = $env:POWER_AUTOMATE_WEBHOOK_URL,
    [switch]$EnableRpa84,
    [switch]$FailOnWarn,
    [switch]$RunWatchdogBefore,
    [string]$WatchdogReportPath = "",
    [double]$WatchdogMaxAgeHours = 14,
    [int]$WatchdogMinScreenshots = 7,
    [switch]$WatchdogWarnIsFailure
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

if (-not $Python) {
    $venvPython = Join-Path $RepoRoot "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $Python = $venvPython
    } else {
        $Python = "python"
    }
}

Set-Location $RepoRoot

if ($RunWatchdogBefore) {
    $watchdog = Join-Path $RepoRoot "scripts\taiwanlife_watchdog.ps1"
    if (-not (Test-Path $watchdog)) {
        throw "找不到 watchdog：$watchdog"
    }
    if (-not $WatchdogReportPath) {
        $WatchdogReportPath = Join-Path $OutputDir "latest.json"
    }

    $watchdogArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $watchdog,
        "-ReportPath", $WatchdogReportPath,
        "-MaxAgeHours", $WatchdogMaxAgeHours,
        "-MinScreenshots", $WatchdogMinScreenshots
    )
    if ($WatchdogWarnIsFailure) {
        $watchdogArgs += "-WarnIsFailure"
    }

    $watchdogOutput = & powershell.exe @watchdogArgs 2>&1
    $watchdogExitCode = $LASTEXITCODE
    $watchdogOutput | ForEach-Object { Write-Output $_ }

    if ($watchdogExitCode -ne 0) {
        $detail = ($watchdogOutput | Out-String).Trim()
        $payload = [pscustomobject]@{
            ok = $false
            run_id = ""
            target_name = "台灣人壽官網"
            scheduler = $Scheduler
            summary = [pscustomobject]@{
                total = 1
                pass = 0
                warn = 0
                fail = 1
            }
            problem_checks = @(
                [pscustomobject]@{
                    id = "watchdog"
                    name = "Watchdog 漏跑與異常檢查"
                    status = "fail"
                    detail = $detail
                }
            )
            latest_json = $WatchdogReportPath
            latest_md = ""
            screenshots = @()
            email_sent = $false
            summary_text = $detail
        }
        $json = $payload | ConvertTo-Json -Depth 10
        Write-Output $json
        if ($PowerAutomateWebhookUrl) {
            Invoke-RestMethod `
                -Uri $PowerAutomateWebhookUrl `
                -Method Post `
                -ContentType "application/json; charset=utf-8" `
                -Body $json | Out-Null
        }
        exit 1
    }
}

$monitorArgs = @(
    "-m", "taiwanlife_monitor.monitor",
    "--config", $Config,
    "--output-dir", $OutputDir,
    "--scheduler", $Scheduler,
    "--fail-exit-code"
)

if ($EnableRpa84) {
    $monitorArgs += "--enable-rpa84"
}

$output = & $Python @monitorArgs 2>&1
$exitCode = $LASTEXITCODE
$output | ForEach-Object { Write-Output $_ }

$jsonLine = $output | Where-Object { $_ -match "^\s*\{" } | Select-Object -Last 1
if (-not $jsonLine) {
    Write-Error "monitor stdout 找不到 JSON payload"
    exit 1
}

$payload = $jsonLine | ConvertFrom-Json
$warnCount = 0
$failCount = 0
if ($payload.summary -and $null -ne $payload.summary.warn) {
    $warnCount = [int]$payload.summary.warn
}
if ($payload.summary -and $null -ne $payload.summary.fail) {
    $failCount = [int]$payload.summary.fail
}
$shouldNotify = ($failCount -gt 0) -or ($warnCount -gt 0)

if ($PowerAutomateWebhookUrl -and $shouldNotify) {
    $body = $payload | ConvertTo-Json -Depth 10
    Invoke-RestMethod `
        -Uri $PowerAutomateWebhookUrl `
        -Method Post `
        -ContentType "application/json; charset=utf-8" `
        -Body $body | Out-Null
}

if ($FailOnWarn -and $warnCount -gt 0 -and $exitCode -eq 0) {
    exit 2
}

exit $exitCode

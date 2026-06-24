param(
    [string]$ReportPath = "reports\latest.json",
    [double]$MaxAgeHours = 14,
    [int]$MinScreenshots = 7,
    [switch]$WarnIsFailure
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ReportPath)) {
    Write-Error "WATCHDOG: report not found: $ReportPath"
    exit 1
}

try {
    $report = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Write-Error "WATCHDOG: cannot parse JSON report ${ReportPath}: $($_.Exception.Message)"
    exit 1
}

$errors = New-Object System.Collections.Generic.List[string]
$summary = $report.summary
$failCount = 0
$warnCount = 0
if ($summary -and $null -ne $summary.fail) { $failCount = [int]$summary.fail }
if ($summary -and $null -ne $summary.warn) { $warnCount = [int]$summary.warn }

$timestamp = $report.finished_at
if (-not $timestamp) { $timestamp = $report.started_at }
try {
    $finishedAt = [datetimeoffset]::Parse([string]$timestamp)
    $ageHours = ([datetimeoffset]::UtcNow - $finishedAt.ToUniversalTime()).TotalHours
    if ($ageHours -gt $MaxAgeHours) {
        $errors.Add(("latest report is stale: age={0:N1}h > {1:g}h" -f $ageHours, $MaxAgeHours))
    }
} catch {
    $ageHours = $null
    $errors.Add("cannot parse finished_at/started_at: $($_.Exception.Message)")
}

if ($failCount -gt 0) { $errors.Add("report has fail=$failCount") }
if ($WarnIsFailure -and $warnCount -gt 0) { $errors.Add("report has warn=$warnCount") }

$screenshots = if ($report.screenshots) { @($report.screenshots) } else { @() }
if ($screenshots.Count -lt $MinScreenshots) {
    $errors.Add("not enough screenshots: $($screenshots.Count) < $MinScreenshots")
}

$runId = $report.run_id
if (-not $runId) { $runId = "(unknown)" }

if ($errors.Count -gt 0) {
    Write-Output "WATCHDOG: abnormal run_id=$runId fail=$failCount warn=$warnCount screenshots=$($screenshots.Count) report=$ReportPath"
    foreach ($item in $errors) { Write-Output "- $item" }
    exit 1
}

if ($null -ne $ageHours) {
    Write-Output ("WATCHDOG: ok run_id={0} fail={1} warn={2} screenshots={3} age_hours={4:N1} report={5}" -f $runId, $failCount, $warnCount, $screenshots.Count, $ageHours, $ReportPath)
} else {
    Write-Output "WATCHDOG: ok run_id=$runId fail=$failCount warn=$warnCount screenshots=$($screenshots.Count) report=$ReportPath"
}

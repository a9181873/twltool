param(
    [string]$RepoRoot = "",
    [string]$Python = "",
    [string]$Config = "config\taiwanlife.json",
    [string]$OutputDir = "reports",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8787,
    [string]$Token = $env:FLOW_UI_TOKEN,
    [switch]$NoBrowser
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

if ($HostName -notin @("127.0.0.1", "localhost", "::1") -and -not $Token) {
    throw "Token is required when HostName is not local."
}

Set-Location $RepoRoot

$argsList = @(
    "-m", "taiwanlife_monitor.flow_ui",
    "--config", $Config,
    "--output-dir", $OutputDir,
    "--host", $HostName,
    "--port", $Port
)

if ($Token) {
    $argsList += @("--token", $Token)
}
if ($NoBrowser) {
    $argsList += "--no-browser"
}

& $Python @argsList

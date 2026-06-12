param(
    [switch]$GeneratedOnly,
    [switch]$AllLocalData,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DataRoot = Join-Path $ProjectRoot "data"

if (-not $GeneratedOnly -and -not $AllLocalData) {
    $GeneratedOnly = $true
}

if ($GeneratedOnly -and $AllLocalData) {
    throw "Choose either -GeneratedOnly or -AllLocalData, not both."
}

if (-not (Test-Path -LiteralPath $DataRoot)) {
    Write-Host "No data directory found."
    exit 0
}

if ($AllLocalData) {
    $targets = @(
        (Join-Path $DataRoot "pit_market.duckdb"),
        (Join-Path $DataRoot "raw"),
        (Join-Path $DataRoot "staging"),
        (Join-Path $DataRoot "normalized"),
        (Join-Path $DataRoot "research")
    )
}
else {
    $targets = @(
        (Join-Path $DataRoot "pit_market.duckdb"),
        (Join-Path $DataRoot "staging"),
        (Join-Path $DataRoot "normalized"),
        (Join-Path $DataRoot "research")
    )
}

$resolvedDataRoot = (Resolve-Path -LiteralPath $DataRoot).Path
$existingTargets = @()

foreach ($target in $targets) {
    if (Test-Path -LiteralPath $target) {
        $resolvedTarget = (Resolve-Path -LiteralPath $target).Path
        if (-not $resolvedTarget.StartsWith($resolvedDataRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove path outside data root: $resolvedTarget"
        }
        $existingTargets += $resolvedTarget
    }
}

if ($existingTargets.Count -eq 0) {
    Write-Host "No local data artifacts found."
    exit 0
}

Write-Host "FONA local data reset"
Write-Host "Project: $ProjectRoot"
Write-Host "Mode: $(if ($AllLocalData) { 'all local data' } else { 'generated artifacts only' })"
Write-Host "Targets:"
$existingTargets | ForEach-Object { Write-Host "  $_" }

if (-not $Force) {
    Write-Host ""
    Write-Host "Preview only. Re-run with -Force to remove these paths."
    exit 0
}

foreach ($target in $existingTargets) {
    Remove-Item -LiteralPath $target -Recurse -Force
    Write-Host "Removed $target"
}

foreach ($dir in @("raw", "staging", "normalized", "research")) {
    $path = Join-Path $DataRoot $dir
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $path ".gitkeep") -Force | Out-Null
}

foreach ($dir in @("raw\sec", "raw\fmp", "raw\kaggle_delisted", "raw\stooq", "raw\yahoo")) {
    $path = Join-Path $DataRoot $dir
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $path ".gitkeep") -Force | Out-Null
}

Write-Host "Local data state reset complete."

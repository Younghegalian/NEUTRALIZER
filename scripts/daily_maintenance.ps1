$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = if ($env:NEUTRALIZER_PYTHON) { $env:NEUTRALIZER_PYTHON } else { "python" }
$StartDate = if ($env:NEUTRALIZER_START_DATE) { $env:NEUTRALIZER_START_DATE } else { "2010-01-01" }
$YahooWorkers = if ($env:NEUTRALIZER_YAHOO_WORKERS) { $env:NEUTRALIZER_YAHOO_WORKERS } else { "6" }
$Year = (Get-Date).Year
$Quarter = [Math]::Floor(((Get-Date).Month - 1) / 3) + 1

Write-Host "NEUTRALIZER daily maintenance"
Write-Host "Project: $ProjectRoot"
Write-Host "Python: $Python"
Write-Host "Date range: $StartDate to today"

$secIndex = Join-Path $ProjectRoot "data\raw\sec\full-index\${Year}q${Quarter}_master.idx"
$secForm345 = Join-Path $ProjectRoot "data\raw\sec\form345\${Year}q${Quarter}_form345.zip"

foreach ($path in @($secIndex, $secForm345)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
        Write-Host "Refreshed cache by removing $path"
    }
}

& $Python -m src.run_pipeline --step check
& $Python -m src.run_pipeline --step collect_yahoo_active --start-date $StartDate --end-date today --yahoo-workers $YahooWorkers --force-yahoo-refresh
& $Python -m src.run_pipeline --step collect_sec_delisted_candidates --sec-start-year 2010 --skip-sec-doc-enrich
& $Python -m src.run_pipeline --step probe_yahoo_delisted --start-date $StartDate --end-date today --yahoo-workers $YahooWorkers
& $Python -m src.run_pipeline --step load_kaggle_delisted --start-date $StartDate --end-date today
& $Python -m src.run_pipeline --step fmp_metadata --start-date $StartDate --end-date today
& $Python -m src.run_pipeline --step normalize --start-date $StartDate --end-date today
& $Python -m src.run_pipeline --step liquidity
& $Python -m src.run_pipeline --step universe
& $Python -m src.run_pipeline --step duckdb
& $Python -m unittest discover -s tests

Write-Host "NEUTRALIZER daily maintenance complete."


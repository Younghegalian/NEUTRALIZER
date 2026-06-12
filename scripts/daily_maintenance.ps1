$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Test-PythonCandidate {
    param([string]$Candidate)

    try {
        & $Candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Resolve-FonaPython {
    $pythonOverride = if ($env:FONA_PYTHON) { $env:FONA_PYTHON } else { $null }
    if ($pythonOverride) {
        if (Test-PythonCandidate -Candidate $pythonOverride) {
            return $pythonOverride
        }
        throw "FONA_PYTHON is set but is not a usable Python 3.10+ executable: $pythonOverride"
    }

    $candidates = @()
    foreach ($commandName in @("python", "python3")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command -and $command.Source -and $command.Source -notlike "*\Microsoft\WindowsApps\*") {
            $candidates += $command.Source
        }
    }

    $candidates += Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    $candidates += Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if ((Test-Path -LiteralPath $candidate) -and (Test-PythonCandidate -Candidate $candidate)) {
            return $candidate
        }
    }

    throw "No usable Python 3.10+ executable found. Set FONA_PYTHON to your Python path."
}

$Python = Resolve-FonaPython
$StartDate = if ($env:FONA_START_DATE) { $env:FONA_START_DATE } else { "2010-01-01" }
$YahooWorkers = if ($env:FONA_YAHOO_WORKERS) { $env:FONA_YAHOO_WORKERS } else { "6" }
$FmpProfileLimit = if ($env:FONA_FMP_PROFILE_LIMIT) { $env:FONA_FMP_PROFILE_LIMIT } else { "0" }
$SecCompanyLimit = if ($env:FONA_SEC_COMPANY_LIMIT) { $env:FONA_SEC_COMPANY_LIMIT } else { "0" }
$SecCompanyArgs = @("--sec-company-limit", $SecCompanyLimit)
if ($env:FONA_SEC_COMPANY_USE_BULK -eq "1") {
    $SecCompanyArgs += "--sec-company-use-bulk"
}
if ($env:FONA_FORCE_SEC_COMPANY_BULK_DOWNLOAD -eq "1") {
    $SecCompanyArgs += "--force-sec-company-bulk-download"
}
$Year = (Get-Date).Year
$Quarter = [Math]::Floor(((Get-Date).Month - 1) / 3) + 1

Write-Host "FONA daily maintenance"
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
& $Python -m src.run_pipeline --step fmp_profiles --fmp-profile-limit $FmpProfileLimit
& $Python -m src.run_pipeline --step sec_company_metadata @SecCompanyArgs
& $Python -m src.run_pipeline --step security_master
& $Python -m src.run_pipeline --step corporate_action_evidence
& $Python -m src.run_pipeline --step liquidity
& $Python -m src.run_pipeline --step universe
& $Python -m src.run_pipeline --step backtest_universe
& $Python -m src.run_pipeline --step delisting_outcomes
& $Python -m src.run_pipeline --step terminal_event_validity
& $Python -m src.run_pipeline --step symbol_aliases
& $Python -m src.run_pipeline --step duckdb
& $Python -m src.tools.audit_daily_prices

$MarketFlowArgs = @("--output", "data\research\market_flow_audit.csv")
if ($env:FONA_FETCH_MARKET_FLOW_BENCHMARKS -eq "1") {
    $MarketFlowArgs += "--fetch-benchmarks"
}
& $Python -m src.tools.audit_market_flows @MarketFlowArgs

& $Python -m unittest discover -s tests

Write-Host "FONA daily maintenance complete."

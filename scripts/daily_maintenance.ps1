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

function Resolve-NeutralizerPython {
    if ($env:NEUTRALIZER_PYTHON) {
        if (Test-PythonCandidate -Candidate $env:NEUTRALIZER_PYTHON) {
            return $env:NEUTRALIZER_PYTHON
        }
        throw "NEUTRALIZER_PYTHON is set but is not a usable Python 3.10+ executable: $env:NEUTRALIZER_PYTHON"
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

    throw "No usable Python 3.10+ executable found. Set NEUTRALIZER_PYTHON to your Python path."
}

$Python = Resolve-NeutralizerPython
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

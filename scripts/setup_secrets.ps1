param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

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
    if ($env:FONA_PYTHON) {
        if (Test-PythonCandidate -Candidate $env:FONA_PYTHON) {
            return $env:FONA_PYTHON
        }
        throw "FONA_PYTHON is set but is not a usable Python 3.10+ executable: $env:FONA_PYTHON"
    }

    foreach ($commandName in @("python", "python3")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command -and $command.Source -and $command.Source -notlike "*\Microsoft\WindowsApps\*") {
            if (Test-PythonCandidate -Candidate $command.Source) {
                return $command.Source
            }
        }
    }

    foreach ($candidate in @(
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
        (Join-Path $ProjectRoot ".venv\bin\python"),
        (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
    )) {
        if ((Test-Path -LiteralPath $candidate) -and (Test-PythonCandidate -Candidate $candidate)) {
            return $candidate
        }
    }

    throw "No usable Python 3.10+ executable found. Set FONA_PYTHON to your Python path."
}

$Python = Resolve-FonaPython
& $Python (Join-Path $PSScriptRoot "setup_secrets.py") @ExtraArgs
exit $LASTEXITCODE

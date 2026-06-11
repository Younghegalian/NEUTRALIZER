$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Read-SecretPlain {
    param([string]$Prompt)

    $secure = Read-Host -Prompt $Prompt -AsSecureString
    if ($secure.Length -eq 0) {
        return ""
    }

    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Set-LocalEnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )

    $lines = @()
    if (Test-Path -LiteralPath $Path) {
        $lines = Get-Content -LiteralPath $Path | Where-Object {
            $_ -notmatch "^\s*$([Regex]::Escape($Key))="
        }
    }

    if ($Value) {
        $lines += "$Key=$Value"
    }

    Set-Content -LiteralPath $Path -Value $lines -Encoding UTF8
}

$kaggleToken = Read-SecretPlain "KAGGLE_API_TOKEN"
$fmpKey = Read-SecretPlain "FMP_API_KEY optional, press Enter to skip"

if ($kaggleToken) {
    $kaggleDir = Join-Path $env:USERPROFILE ".kaggle"
    New-Item -ItemType Directory -Force -Path $kaggleDir | Out-Null
    $accessTokenPath = Join-Path $kaggleDir "access_token"
    Set-Content -LiteralPath $accessTokenPath -Value $kaggleToken -NoNewline -Encoding ASCII
    Write-Host "Saved Kaggle token to $accessTokenPath"
}
else {
    Write-Host "Skipped Kaggle token."
}

$envPath = Join-Path $ProjectRoot ".env.local"
Set-LocalEnvValue -Path $envPath -Key "FMP_API_KEY" -Value $fmpKey
if ($fmpKey) {
    Write-Host "Saved FMP key to $envPath"
}
else {
    Write-Host "Skipped FMP key."
}

Write-Host "Done. Run: python -m src.run_pipeline --step check"


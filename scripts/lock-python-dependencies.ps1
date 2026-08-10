param(
    [string]$Python = "python.exe"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "apps\backend"
$ToolVersion = "7.5.2"

Write-Host "[Reporter Pro Lock] Installing pip-tools $ToolVersion..." -ForegroundColor Cyan
& $Python -m pip install --disable-pip-version-check "pip-tools==$ToolVersion"
if ($LASTEXITCODE -ne 0) { throw "Could not install pip-tools." }

$ScriptsDirectory = (& $Python -c "import sysconfig; print(sysconfig.get_path('scripts'))").Trim()
$PipCompile = Join-Path $ScriptsDirectory "pip-compile.exe"
if (-not (Test-Path -LiteralPath $PipCompile)) {
    $PipCompile = (Get-Command "pip-compile.exe" -ErrorAction Stop).Source
}

function Compile-Lock([string]$InputName, [string]$OutputName) {
    Write-Host "[Reporter Pro Lock] $InputName -> $OutputName" -ForegroundColor Cyan
    $InputPath = Join-Path $Backend $InputName
    $OutputPath = Join-Path $Backend $OutputName
    & $PipCompile `
        --generate-hashes `
        --resolver=backtracking `
        --strip-extras `
        --no-emit-index-url `
        --no-emit-trusted-host `
        --newline=lf `
        --output-file $OutputPath `
        $InputPath
    if ($LASTEXITCODE -ne 0) { throw "Could not compile $OutputName." }
}

Compile-Lock "requirements.txt" "requirements.lock.txt"
Compile-Lock "requirements-dev.txt" "requirements-dev.lock.txt"

Write-Host "[Reporter Pro Lock] Lockfiles regenerated with hashes." -ForegroundColor Green

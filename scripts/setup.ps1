param(
    [switch]$Development,
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "apps\backend"
$Frontend = Join-Path $Root "apps\frontend"
$Venv = Join-Path $Backend ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$Requirements = if ($Development) { "requirements-dev.txt" } else { "requirements.txt" }

function Write-Step([string]$Message) {
    Write-Host "[Reporter Pro Setup] $Message" -ForegroundColor Cyan
}

function Require-Command([string]$Name, [string]$InstallHint) {
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Command) {
        throw "'$Name' was not found. $InstallHint"
    }
    return $Command.Source
}

$Python = Require-Command "python.exe" "Install Python 3.12 and enable 'Add Python to PATH'."
$Npm = Require-Command "npm.cmd" "Install Node.js 20 LTS (npm 10 or newer)."
$Node = Require-Command "node.exe" "Install Node.js 20 LTS."

$PythonVersion = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
if ($LASTEXITCODE -ne 0 -or [version]$PythonVersion -lt [version]"3.12") {
    throw "Python 3.12 or newer is required; found $PythonVersion."
}

$NodeVersion = [version]((& $Node -p "process.versions.node").Trim())
if ($LASTEXITCODE -ne 0 -or $NodeVersion -lt [version]"20.19.0" -or $NodeVersion -ge [version]"26.0.0") {
    throw "Node.js 20.19-25.x is required; found $(& $Node --version)."
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Step "Creating isolated Python environment..."
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python environment." }
}

Write-Step "Installing backend dependencies from $Requirements..."
& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $Backend $Requirements)
if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }

if (-not (Test-Path -LiteralPath (Join-Path $Root ".env"))) {
    Copy-Item -LiteralPath (Join-Path $Root ".env.example") -Destination (Join-Path $Root ".env")
    Write-Step "Created local .env from .env.example."
}

Write-Step "Installing locked frontend dependencies..."
Push-Location $Frontend
try {
    & $Npm ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
    if (-not $SkipFrontendBuild) {
        Write-Step "Building the production frontend..."
        & $Npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Reporter Pro is ready." -ForegroundColor Green
Write-Host "Run start.bat for production mode."
if ($Development) {
    Write-Host "Development dependencies were installed. Use scripts\start-reporter.ps1 -Development."
}

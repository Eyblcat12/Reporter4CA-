param(
    [switch]$Development,
    [switch]$SkipFrontendBuild,
    [switch]$UsePrebuiltFrontend,
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "apps\backend"
$Frontend = Join-Path $Root "apps\frontend"
$Venv = Join-Path $Backend ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$Requirements = if ($Development) { "requirements-dev.lock.txt" } else { "requirements.lock.txt" }

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

$Python = if ($PythonExecutable) {
    $ResolvedPython = [System.IO.Path]::GetFullPath($PythonExecutable)
    if (-not (Test-Path -LiteralPath $ResolvedPython -PathType Leaf)) {
        throw "Python executable was not found: $ResolvedPython"
    }
    $ResolvedPython
} else {
    Require-Command "python.exe" "Install Python 3.12 and enable 'Add Python to PATH'."
}
$Npm = $null
$Node = $null
if (-not $UsePrebuiltFrontend) {
    $Npm = Require-Command "npm.cmd" "Install Node.js 20 LTS (npm 10 or newer)."
    $Node = Require-Command "node.exe" "Install Node.js 20 LTS."
}

$PythonVersion = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
if ($LASTEXITCODE -ne 0 -or [version]$PythonVersion -lt [version]"3.12") {
    throw "Python 3.12 or newer is required; found $PythonVersion."
}
$PythonVenvScripts = (& $Python -c "import sysconfig; print(sysconfig.get_path('scripts'))").Trim()
if ($LASTEXITCODE -ne 0 -or (Split-Path -Leaf $PythonVenvScripts) -ne "Scripts") {
    throw "Reporter Pro on Windows requires a native python.org-style Python that creates .venv\Scripts. The selected interpreter appears to use '$PythonVenvScripts'. Install native Python 3.12+ or rerun setup with -PythonExecutable <path-to-python.exe>."
}

if (-not $UsePrebuiltFrontend) {
    $NodeVersion = [version]((& $Node -p "process.versions.node").Trim())
    if ($LASTEXITCODE -ne 0 -or $NodeVersion -lt [version]"20.19.0" -or $NodeVersion -ge [version]"26.0.0") {
        throw "Node.js 20.19-25.x is required; found $(& $Node --version)."
    }
} else {
    $PrebuiltIndex = Join-Path $Frontend "dist\index.html"
    if (-not (Test-Path -LiteralPath $PrebuiltIndex)) {
        throw "Prebuilt frontend is missing from this bundle: $PrebuiltIndex"
    }
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Step "Creating isolated Python environment..."
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python environment." }
}

Write-Step "Installing backend dependencies from $Requirements..."
& $VenvPython -m pip install --disable-pip-version-check --require-hashes -r (Join-Path $Backend $Requirements)
if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }

Write-Step "Preparing bundled DOCX templates for a faster first Preview..."
& $VenvPython (Join-Path $Root "scripts\warm_prepared_templates.py")
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Template warm-up was deferred; Reporter Pro will use the safe cold path."
}

if (-not (Test-Path -LiteralPath (Join-Path $Root ".env"))) {
    Copy-Item -LiteralPath (Join-Path $Root ".env.example") -Destination (Join-Path $Root ".env")
    Write-Step "Created local .env from .env.example."
}

if ($UsePrebuiltFrontend) {
    Write-Step "Using the verified prebuilt production frontend from this release bundle."
} else {
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
}

Write-Host ""
Write-Host "Reporter Pro is ready." -ForegroundColor Green
Write-Host "Run start.bat for production mode."
if ($Development) {
    Write-Host "Development dependencies were installed. Use scripts\start-reporter.ps1 -Development."
}

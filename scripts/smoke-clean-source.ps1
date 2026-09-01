param(
    [string]$Ref = "HEAD",
    [string]$PythonExecutable = "python.exe",
    [switch]$KeepWorkspace,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$VerificationRoot = [System.IO.Path]::GetFullPath((Join-Path $Root "artifacts\verification"))
$RunId = [Guid]::NewGuid().ToString("N")
$RunRoot = Join-Path $VerificationRoot "clean-source-$RunId"
$Archive = Join-Path $RunRoot "source.zip"
$Extract = Join-Path $RunRoot "workspace"
$ResultPath = Join-Path $VerificationRoot "clean-source-latest.json"
$Passed = $false
$Started = Get-Date
$PythonCommand = Get-Command $PythonExecutable -ErrorAction SilentlyContinue
if (-not $PythonCommand) {
    throw "Python executable was not found: $PythonExecutable"
}
$ResolvedPython = [System.IO.Path]::GetFullPath($PythonCommand.Source)

function Write-Step([string]$Message) {
    Write-Host "[Clean Source Smoke] $Message" -ForegroundColor Cyan
}

try {
    New-Item -ItemType Directory -Path $RunRoot -Force | Out-Null
    Write-Step "Creating source archive from $Ref..."
    & git -C $Root archive --format=zip --output=$Archive $Ref
    if ($LASTEXITCODE -ne 0) { throw "git archive failed for $Ref." }
    Expand-Archive -LiteralPath $Archive -DestinationPath $Extract -Force

    Write-Step "Validating tracked source boundary..."
    & $ResolvedPython (Join-Path $Root "scripts\validate_clean_source.py") $Extract
    if ($LASTEXITCODE -ne 0) { throw "Clean source contract failed." }

    if (-not $SkipInstall) {
        Write-Step "Installing locked dependencies and building frontend from clean source..."
        & (Join-Path $Extract "scripts\setup.ps1") -Development -PythonExecutable $ResolvedPython
        if ($LASTEXITCODE -ne 0) { throw "Clean source setup failed." }

        $VenvPython = Join-Path $Extract "apps\backend\.venv\Scripts\python.exe"
        Write-Step "Verifying all bundled templates are prepared..."
        & $VenvPython (Join-Path $Extract "scripts\warm_prepared_templates.py")
        if ($LASTEXITCODE -ne 0) { throw "Bundled template preparation smoke failed." }

        Write-Step "Running backend health smoke from the clean environment..."
        Push-Location (Join-Path $Extract "apps\backend")
        try {
            & $VenvPython -c "from fastapi.testclient import TestClient; from main import app; response=TestClient(app).get('/api/health'); assert response.status_code == 200; assert response.json().get('status') == 'ok'"
            if ($LASTEXITCODE -ne 0) { throw "Backend health smoke failed." }
        } finally {
            Pop-Location
        }
        if (-not (Test-Path -LiteralPath (Join-Path $Extract "apps\frontend\dist\index.html"))) {
            throw "Clean frontend production build is missing."
        }
    }

    $Passed = $true
} finally {
    $Commit = (& git -C $Root rev-list -n 1 $Ref 2>$null).Trim()
    $Result = [ordered]@{
        schemaVersion = 1
        ref = $Ref
        commit = $Commit
        startedAt = $Started.ToUniversalTime().ToString("o")
        finishedAt = (Get-Date).ToUniversalTime().ToString("o")
        installExecuted = -not $SkipInstall
        passed = $Passed
        workspaceRetained = $KeepWorkspace -or -not $Passed
    } | ConvertTo-Json
    New-Item -ItemType Directory -Path $VerificationRoot -Force | Out-Null
    [System.IO.File]::WriteAllText($ResultPath, $Result + [Environment]::NewLine)

    if ($Passed -and -not $KeepWorkspace -and (Test-Path -LiteralPath $RunRoot)) {
        $ResolvedRun = [System.IO.Path]::GetFullPath($RunRoot)
        if (-not $ResolvedRun.StartsWith($VerificationRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean unsafe smoke workspace: $ResolvedRun"
        }
        Remove-Item -LiteralPath $ResolvedRun -Recurse -Force
    }
}

if (-not $Passed) {
    throw "Clean source smoke failed. Diagnostics retained at $RunRoot"
}
Write-Host "Clean source smoke passed for $Ref." -ForegroundColor Green
Write-Host "Result: $ResultPath"

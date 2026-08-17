param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "apps\backend"
$Frontend = Join-Path $Root "apps\frontend"
$Verification = Join-Path $Root ".verification"

function Write-Step([string]$Message) {
    Write-Host "[Reporter Pro Check] $Message" -ForegroundColor Cyan
}

if (-not $SkipBackend) {
    $VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
    $Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
    Write-Step "Running Ruff static analysis and format check..."
    & $Python -m ruff check $Backend (Join-Path $Root "scripts") (Join-Path $Root "tests")
    if ($LASTEXITCODE -ne 0) {
        throw "Python static analysis failed with exit code $LASTEXITCODE."
    }
    & $Python -m ruff format --check $Backend (Join-Path $Root "scripts") (Join-Path $Root "tests")
    if ($LASTEXITCODE -ne 0) {
        throw "Python format check failed with exit code $LASTEXITCODE."
    }
    Write-Step "Running backend regression suite..."
    & $Python -m unittest -v `
        tests.test_api_import `
        tests.test_api_integration `
        tests.test_api_errors `
        tests.test_dashboard_summary `
        tests.test_data_quality `
        tests.test_database_migrations `
        tests.test_docx_field_updater `
        tests.test_docx_golden `
        tests.test_fast_cell_path `
        tests.test_incident_validation `
        tests.test_plugin_manager `
        tests.test_performance_harness `
        tests.test_prepared_template `
        tests.test_preview_benchmark_summary `
        tests.test_preview_artifacts `
        tests.test_report_jobs `
        tests.test_report_generator `
        tests.test_report_integrity `
        tests.test_report_snapshot `
        tests.test_rule_engine `
        tests.test_runtime_lifecycle `
        tests.test_scheduled_backup `
        tests.test_system_health `
        tests.test_soak_harness `
        tests.test_template_categories `
        tests.test_template_blueprint `
        tests.test_compact_prototype_integration `
        tests.test_template_schema `
        tests.test_threat_intelligence `
        tests.test_tracking_import `
        tests.test_upload_limits `
        tests.test_workspace_backup
    if ($LASTEXITCODE -ne 0) {
        throw "Backend checks failed with exit code $LASTEXITCODE."
    }
}

if (-not $SkipFrontend) {
    $Npm = if (Get-Command "npm.cmd" -ErrorAction SilentlyContinue) { "npm.cmd" } else { "npm" }
    $FrontendOutput = Join-Path $Verification "frontend-dist"
    try {
        Push-Location $Frontend
        Write-Step "Running frontend static analysis..."
        & $Npm run lint
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend lint failed with exit code $LASTEXITCODE."
        }
        & $Npm run format:check
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend format check failed with exit code $LASTEXITCODE."
        }
        Write-Step "Running frontend component tests..."
        & $Npm test
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend tests failed with exit code $LASTEXITCODE."
        }
        Write-Step "Building frontend into an isolated verification directory..."
        & $Npm run build -- --outDir $FrontendOutput --emptyOutDir
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend checks failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
        if (Test-Path -LiteralPath $Verification) {
            $ResolvedRoot = [System.IO.Path]::GetFullPath($Root)
            $ResolvedVerification = [System.IO.Path]::GetFullPath($Verification)
            if (-not $ResolvedVerification.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing to clean unsafe verification path: $ResolvedVerification"
            }
            Remove-Item -LiteralPath $Verification -Recurse -Force
        }
    }
}

Write-Host ""
Write-Host "All requested checks passed." -ForegroundColor Green

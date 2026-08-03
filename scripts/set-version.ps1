param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if ($Version -notmatch '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$') {
    throw "Version must be valid SemVer, for example 2.1.0 or 2.2.0-rc.1."
}

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
function Write-Utf8([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content, $Utf8NoBom)
}
function Replace-Required([string]$Path, [string]$Pattern, [string]$Replacement) {
    $Content = [System.IO.File]::ReadAllText($Path)
    if (-not [regex]::IsMatch($Content, $Pattern)) { throw "Version marker not found in $Path" }
    $Updated = [regex]::Replace($Content, $Pattern, $Replacement)
    Write-Utf8 $Path $Updated
}

Write-Utf8 (Join-Path $Root "VERSION") ($Version + [Environment]::NewLine)
Replace-Required `
    (Join-Path $Root "apps\backend\core\config.py") `
    'APP_VERSION = "[^"]+"' `
    "APP_VERSION = `"$Version`""
Replace-Required `
    (Join-Path $Root "apps\backend\core\workspace_backup.py") `
    'app_version: str = "[^"]+"' `
    "app_version: str = `"$Version`""

$Npm = if (Get-Command "npm.cmd" -ErrorAction SilentlyContinue) { "npm.cmd" } else { "npm" }
Push-Location (Join-Path $Root "apps\frontend")
try {
    & $Npm version $Version --no-git-tag-version --allow-same-version
    if ($LASTEXITCODE -ne 0) { throw "Could not update frontend package versions." }
} finally {
    Pop-Location
}

Write-Host "Reporter Pro source version updated to $Version." -ForegroundColor Green
Write-Host "Add CHANGELOG.md and docs\releases\v$Version.md before tagging."

param(
    [switch]$RequireTag
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content -LiteralPath (Join-Path $Root "VERSION") -Raw).Trim()
if ($Version -notmatch '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$') {
    throw "VERSION is not valid SemVer: $Version"
}

$Config = Get-Content -LiteralPath (Join-Path $Root "apps\backend\core\config.py") -Raw
if ($Config -notmatch ('APP_VERSION = "' + [regex]::Escape($Version) + '"')) {
    throw "Backend APP_VERSION does not match VERSION ($Version)."
}
$Backup = Get-Content -LiteralPath (Join-Path $Root "apps\backend\core\workspace_backup.py") -Raw
if ($Backup -notmatch ('app_version: str = "' + [regex]::Escape($Version) + '"')) {
    throw "Workspace backup version does not match VERSION ($Version)."
}
$Package = Get-Content -LiteralPath (Join-Path $Root "apps\frontend\package.json") -Raw | ConvertFrom-Json
$PackageLockText = Get-Content -LiteralPath (Join-Path $Root "apps\frontend\package-lock.json") -Raw
$PackageLockVersions = [regex]::Matches($PackageLockText, '"version"\s*:\s*"([^"]+)"')
if (
    $Package.version -ne $Version -or
    $PackageLockVersions.Count -lt 2 -or
    $PackageLockVersions[0].Groups[1].Value -ne $Version -or
    $PackageLockVersions[1].Groups[1].Value -ne $Version
) {
    throw "Frontend package versions do not match VERSION ($Version)."
}
$Changelog = Get-Content -LiteralPath (Join-Path $Root "CHANGELOG.md") -Raw
if ($Changelog -notmatch ('(?m)^## \[' + [regex]::Escape($Version) + '\] - \d{4}-\d{2}-\d{2}$')) {
    throw "CHANGELOG.md has no dated section for $Version."
}
$ReleaseNotes = Join-Path $Root "docs\releases\v$Version.md"
if (-not (Test-Path -LiteralPath $ReleaseNotes)) {
    throw "Release notes are missing: $ReleaseNotes"
}

if ($RequireTag) {
    $Tag = (& git -C $Root describe --tags --exact-match HEAD 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $Tag -ne "v$Version") {
        throw "HEAD must be tagged exactly v$Version before publishing."
    }
}

Write-Host "Release metadata is consistent for v$Version." -ForegroundColor Green

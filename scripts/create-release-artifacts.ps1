param(
    [string]$Ref = "HEAD",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content -LiteralPath (Join-Path $Root "VERSION") -Raw).Trim()
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $Root "artifacts\releases\v$Version"
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$ArtifactRoot = [System.IO.Path]::GetFullPath((Join-Path $Root "artifacts\releases"))
if (-not $OutputDirectory.StartsWith($ArtifactRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Release output must stay under $ArtifactRoot"
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$Prefix = "ReporterPro-$Version/"
$Zip = Join-Path $OutputDirectory "reporter-pro-v$Version-source.zip"
$Tar = Join-Path $OutputDirectory "reporter-pro-v$Version-source.tar.gz"
$WindowsBundle = Join-Path $OutputDirectory "reporter-pro-v$Version-windows-prebuilt.zip"
& git -C $Root archive --format=zip --prefix=$Prefix --output=$Zip $Ref
if ($LASTEXITCODE -ne 0) { throw "Could not create source ZIP from $Ref." }
& git -C $Root archive --format=tar.gz --prefix=$Prefix --output=$Tar $Ref
if ($LASTEXITCODE -ne 0) { throw "Could not create source TAR.GZ from $Ref." }

$FrontendDist = Join-Path $Root "apps\frontend\dist"
$FrontendIndex = Join-Path $FrontendDist "index.html"
if (-not (Test-Path -LiteralPath $FrontendIndex)) {
    throw "Frontend production build is missing. Run npm run build before creating release artifacts."
}
$Commit = (& git -C $Root rev-list -n 1 $Ref).Trim()
if ($LASTEXITCODE -ne 0 -or $Commit -notmatch '^[0-9a-f]{40}$') {
    throw "Could not resolve release ref $Ref to one Git commit."
}
$Staging = Join-Path $ArtifactRoot (".staging-" + [Guid]::NewGuid().ToString("N"))
try {
    Expand-Archive -LiteralPath $Zip -DestinationPath $Staging -Force
    $BundleRoot = Join-Path $Staging "ReporterPro-$Version"
    if (-not (Test-Path -LiteralPath (Join-Path $BundleRoot "setup-prebuilt.bat"))) {
        throw "Release ref does not contain setup-prebuilt.bat."
    }
    $BundleDist = Join-Path $BundleRoot "apps\frontend\dist"
    New-Item -ItemType Directory -Path $BundleDist -Force | Out-Null
    Copy-Item -Path (Join-Path $FrontendDist "*") -Destination $BundleDist -Recurse -Force
    $Manifest = [ordered]@{
        schemaVersion = 1
        app = "Reporter Pro"
        version = $Version
        gitCommit = $Commit
        createdAt = (Get-Date).ToUniversalTime().ToString("o")
        platform = "windows"
        frontendPrebuilt = $true
        pythonDependencies = "locked-download"
    } | ConvertTo-Json
    [System.IO.File]::WriteAllText(
        (Join-Path $BundleRoot "BUNDLE-MANIFEST.json"),
        $Manifest + [Environment]::NewLine,
        (New-Object System.Text.UTF8Encoding($false))
    )
    Compress-Archive -Path $BundleRoot -DestinationPath $WindowsBundle -Force
} finally {
    if (Test-Path -LiteralPath $Staging) {
        $ResolvedStaging = [System.IO.Path]::GetFullPath($Staging)
        if (-not $ResolvedStaging.StartsWith($ArtifactRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean unsafe staging path: $ResolvedStaging"
        }
        Remove-Item -LiteralPath $ResolvedStaging -Recurse -Force
    }
}

$Checksum = Join-Path $OutputDirectory "SHA256SUMS.txt"
$Lines = @($Zip, $Tar, $WindowsBundle) | ForEach-Object {
    $Hash = (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Hash  $([System.IO.Path]::GetFileName($_))"
}
[System.IO.File]::WriteAllLines(
    $Checksum,
    $Lines,
    (New-Object System.Text.UTF8Encoding($false))
)

foreach ($Line in $Lines) {
    $Parts = $Line -split '  ', 2
    $Actual = (Get-FileHash -LiteralPath (Join-Path $OutputDirectory $Parts[1]) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $Parts[0]) { throw "Checksum verification failed for $($Parts[1])." }
}

Write-Host "Release artifacts and checksums created in $OutputDirectory" -ForegroundColor Green
Get-ChildItem -LiteralPath $OutputDirectory | Select-Object Name, Length

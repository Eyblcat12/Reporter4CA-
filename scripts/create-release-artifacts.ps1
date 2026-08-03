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
& git -C $Root archive --format=zip --prefix=$Prefix --output=$Zip $Ref
if ($LASTEXITCODE -ne 0) { throw "Could not create source ZIP from $Ref." }
& git -C $Root archive --format=tar.gz --prefix=$Prefix --output=$Tar $Ref
if ($LASTEXITCODE -ne 0) { throw "Could not create source TAR.GZ from $Ref." }

$Checksum = Join-Path $OutputDirectory "SHA256SUMS.txt"
$Lines = @($Zip, $Tar) | ForEach-Object {
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

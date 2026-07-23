param(
    [switch]$Development
)

$ErrorActionPreference = "Stop"
$Utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $Utf8
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8

$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "apps\backend"
$FrontendDir = Join-Path $Root "apps\frontend"
$LogDir = Join-Path $Root "logs"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackendLog = Join-Path $LogDir "backend-$Timestamp.log"
$FrontendLog = Join-Path $LogDir "frontend-$Timestamp.log"
$Processes = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

# Some shells (including Codex/MSYS environments) can inject both `Path` and
# `PATH`. Windows PowerShell's Start-Process treats them as duplicate keys and
# fails before launching anything, so keep one canonical process-level value.
$ProcessPath = $env:Path
if ($ProcessPath) {
    [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
    [Environment]::SetEnvironmentVariable("Path", $ProcessPath, "Process")
}

function Write-Step([string]$Message) {
    Write-Host "[Reporter Pro] $Message" -ForegroundColor Cyan
}

function Require-Command([string]$Name) {
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Command) {
        throw "Command '$Name' was not found in PATH."
    }
    return $Command.Source
}

function Test-HttpReady([string]$Url) {
    try {
        $Response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Resolve-ServicePort([int]$Port, [string]$HealthUrl, [string]$ServiceName) {
    $Listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $Listener) {
        return $false
    }

    foreach ($Item in $Listener) {
        $OwnerPid = $Item.OwningProcess
        $Owner = Get-CimInstance Win32_Process -Filter "ProcessId = $OwnerPid" -ErrorAction SilentlyContinue
        $Identity = "$($Owner.ExecutablePath) $($Owner.CommandLine)"
        if ($Owner -and $Identity.IndexOf($Root, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            if (Test-HttpReady $HealthUrl) {
                Write-Step "$ServiceName is already running (PID $OwnerPid); reusing it."
                return $true
            }
            Write-Step "Cleaning unresponsive Reporter Pro $ServiceName process PID $OwnerPid..."
            Stop-Process -Id $OwnerPid -Force -ErrorAction Stop
            continue
        }
        throw "Port $Port is used by PID $OwnerPid, which does not belong to Reporter Pro."
    }

    Start-Sleep -Milliseconds 500
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $Port is still busy after cleaning the unresponsive Reporter Pro process."
    }
    return $false
}

function Wait-Http([string]$Url, [System.Diagnostics.Process]$Process, [int]$TimeoutSeconds = 30) {
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        if ($Process.HasExited) {
            throw "Process PID $($Process.Id) exited before it became ready."
        }
        try {
            $Response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) {
                return
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "Timed out waiting for $Url."
}

function Stop-OwnedProcesses {
    foreach ($Process in $Processes) {
        try {
            if (-not $Process.HasExited) {
                Write-Step "Stopping PID $($Process.Id)..."
                Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
            Write-Warning "Could not stop PID $($Process.Id): $($_.Exception.Message)"
        }
    }
}

try {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor DarkCyan
    Write-Host " Reporter Pro - Application Launcher" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor DarkCyan
    Write-Host ""

    $VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
    $Python = if (Test-Path $VenvPython) { $VenvPython } else { Require-Command "python.exe" }
    $ReuseBackend = Resolve-ServicePort 8000 "http://127.0.0.1:8000/api/health" "backend"
    $ReuseFrontend = $false
    if ($Development) {
        $Npm = Require-Command "npm.cmd"
        $ReuseFrontend = Resolve-ServicePort 5173 "http://127.0.0.1:5173" "frontend"
        if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
            throw "apps\frontend\node_modules is missing. Run 'npm install' in apps\frontend first."
        }
    } elseif (-not (Test-Path (Join-Path $FrontendDir "dist\index.html"))) {
        throw "Frontend production build is missing. Run 'npm run build' in apps\frontend first."
    }

    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

    if (-not $ReuseBackend) {
        Write-Step "Starting backend..."
        # Run one uvicorn process so cleanup owns the actual server PID (no reload child).
        $Backend = Start-Process -FilePath $Python `
            -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000" `
            -WorkingDirectory $BackendDir `
            -RedirectStandardOutput $BackendLog -RedirectStandardError "$BackendLog.err" -PassThru -WindowStyle Hidden
        $Processes.Add($Backend)
        Wait-Http "http://127.0.0.1:8000/api/health" $Backend 30
        Write-Step "Backend ready (PID $($Backend.Id))."
    }

    if ($Development -and -not $ReuseFrontend) {
        Write-Step "Starting frontend..."
        $Frontend = Start-Process -FilePath $Npm -ArgumentList "run", "dev", "--", "--host", "127.0.0.1" `
            -WorkingDirectory $FrontendDir -RedirectStandardOutput $FrontendLog `
            -RedirectStandardError "$FrontendLog.err" -PassThru -WindowStyle Hidden
        $Processes.Add($Frontend)
        Wait-Http "http://127.0.0.1:5173" $Frontend 45
        Write-Step "Frontend ready (PID $($Frontend.Id))."
    }

    Write-Host ""
    if ($Development) {
        $AppUrl = "http://127.0.0.1:5173"
    } else {
        # A build-specific query prevents an already-open browser tab from
        # reusing a stale index.html after the production frontend changes.
        $FrontendIndex = Join-Path $FrontendDir "dist\index.html"
        $BuildStamp = (Get-Item -LiteralPath $FrontendIndex).LastWriteTimeUtc.Ticks
        $AppUrl = "http://127.0.0.1:8000/?build=$BuildStamp"
    }
    $Mode = if ($Development) { "development" } else { "production" }
    Write-Host "Mode:     $Mode"
    Write-Host "App:      $AppUrl" -ForegroundColor Green
    Write-Host "API:      http://127.0.0.1:8000" -ForegroundColor Green
    Write-Host "API Docs: http://127.0.0.1:8000/docs" -ForegroundColor Green
    Write-Host "Logs:     $LogDir"
    Write-Host ""

    Start-Process $AppUrl
    Write-Host "Press ENTER to stop Reporter Pro..."
    [void](Read-Host)
} catch {
    Write-Host ""
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Backend log: $BackendLog"
    Write-Host "Frontend log: $FrontendLog"
    exit 1
} finally {
    Stop-OwnedProcesses
}

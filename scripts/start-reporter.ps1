param(
    [switch]$Development,
    [switch]$NoBrowser,
    [switch]$ExitAfterReady
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
$LauncherId = [Guid]::NewGuid().ToString("N")
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$RunTag = "$Timestamp-$($LauncherId.Substring(0, 8))"
$BackendLog = Join-Path $LogDir "backend-$RunTag.log"
$FrontendLog = Join-Path $LogDir "frontend-$RunTag.log"
$BackendProcess = $null
$FrontendProcess = $null
$BackendIdentity = $null
$StartedBackend = $false
$LauncherAttached = $false
$LauncherOwnershipLost = $false
$LauncherMutex = $null
$MutexAcquired = $false
$LifecyclePayload = $null
$RuntimeProtocolVersion = 2

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

function Get-WorkspaceFingerprint([string]$Path) {
    $Normalized = [System.IO.Path]::GetFullPath($Path)
    $Normalized = $Normalized.Replace("\", "/")
    $Normalized = $Normalized.TrimEnd("/").ToLowerInvariant()
    $Sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $Bytes = [System.Text.Encoding]::UTF8.GetBytes($Normalized)
        $Hash = $Sha256.ComputeHash($Bytes)
        $Hex = -join ($Hash | ForEach-Object { $_.ToString("x2") })
        return $Hex.Substring(0, 24)
    } finally {
        $Sha256.Dispose()
    }
}

function Get-ReporterBackendIdentity(
    [string]$HealthUrl,
    [string]$RuntimeUrl,
    [string]$ExpectedWorkspace
) {
    try {
        $Health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
    } catch {
        return $null
    }
    if ($Health.status -ne "ok" -or $Health.app -ne "Reporter Pro") {
        return $null
    }

    try {
        $Runtime = Invoke-RestMethod -Uri $RuntimeUrl -TimeoutSec 2
    } catch {
        throw "Port 8000 responds as Reporter Pro, but its runtime contract is unavailable. Stop the outdated backend and retry."
    }

    $Properties = @($Runtime.PSObject.Properties.Name)
    $RequiredProperties = @(
        "runtimeProtocolVersion",
        "instanceId",
        "workspaceFingerprint",
        "processId",
        "launcherLeaseActive",
        "activeBrowserSessions",
        "activeOperations",
        "shouldShutdown"
    )
    foreach ($Name in $RequiredProperties) {
        if ($Properties -notcontains $Name) {
            throw "Port 8000 is running an outdated Reporter Pro backend. Close it once, then start Reporter Pro again."
        }
    }
    if ([int]$Runtime.runtimeProtocolVersion -ne $RuntimeProtocolVersion) {
        throw "Reporter Pro runtime protocol $($Runtime.runtimeProtocolVersion) is incompatible with launcher protocol $RuntimeProtocolVersion."
    }
    if ($Runtime.workspaceFingerprint -ne $ExpectedWorkspace) {
        throw "Port 8000 belongs to a different Reporter Pro workspace. Close that instance before starting this checkout."
    }
    if (-not $Runtime.instanceId -or [int]$Runtime.processId -le 0) {
        throw "Reporter Pro returned an invalid runtime identity."
    }
    return $Runtime
}

function Invoke-Lifecycle([string]$Path, [hashtable]$Payload) {
    $Json = $Payload | ConvertTo-Json -Compress
    return Invoke-RestMethod `
        -Uri "http://127.0.0.1:8000/api/runtime/$Path" `
        -Method Post `
        -ContentType "application/json" `
        -Body $Json `
        -TimeoutSec 3
}

function Resolve-ServicePort(
    [int]$Port,
    [string]$HealthUrl,
    [string]$ServiceName,
    [string]$RequiredUrl = "",
    [string]$ExpectedWorkspace = ""
) {
    if ($ServiceName -eq "backend") {
        $VerifiedBackend = Get-ReporterBackendIdentity `
            $HealthUrl `
            $RequiredUrl `
            $ExpectedWorkspace
        if ($VerifiedBackend) {
            $BackendListeners = Get-NetTCPConnection `
                -LocalPort $Port `
                -State Listen `
                -ErrorAction SilentlyContinue
            if (
                $BackendListeners -and
                @($BackendListeners.OwningProcess) -notcontains [int]$VerifiedBackend.processId
            ) {
                throw (
                    "Reporter Pro API identity reports PID $($VerifiedBackend.processId), " +
                    "but port $Port belongs to another process."
                )
            }

            if ([bool]$VerifiedBackend.shutdownRequested) {
                Write-Step "Previous Reporter Pro session is shutting down; waiting for safe completion..."
                $ShutdownDeadline = (Get-Date).AddSeconds(30)
                while ((Get-Date) -lt $ShutdownDeadline) {
                    Start-Sleep -Milliseconds 400
                    $VerifiedBackend = Get-ReporterBackendIdentity `
                        $HealthUrl `
                        $RequiredUrl `
                        $ExpectedWorkspace
                    if (-not $VerifiedBackend) {
                        return $false
                    }
                    if (-not [bool]$VerifiedBackend.shutdownRequested) {
                        break
                    }
                }
                if ($VerifiedBackend -and [bool]$VerifiedBackend.shutdownRequested) {
                    throw (
                        "The previous Reporter Pro session is still finishing " +
                        "$($VerifiedBackend.activeOperations) operation(s). " +
                        "It was left running to protect report data."
                    )
                }
            }

            if ([bool]$VerifiedBackend.launcherLeaseActive -and $MutexAcquired) {
                # Owning the workspace mutex means the previous PowerShell host
                # is gone. Give its short backend lease time to expire, then
                # recover the same healthy backend instead of racing a restart.
                Write-Step "Waiting to recover a stale launcher lease..."
                $LeaseDeadline = (Get-Date).AddSeconds(12)
                while ((Get-Date) -lt $LeaseDeadline) {
                    Start-Sleep -Milliseconds 300
                    $VerifiedBackend = Get-ReporterBackendIdentity `
                        $HealthUrl `
                        $RequiredUrl `
                        $ExpectedWorkspace
                    if (-not $VerifiedBackend) {
                        return $false
                    }
                    if (-not [bool]$VerifiedBackend.launcherLeaseActive) {
                        break
                    }
                }
                if ($VerifiedBackend -and [bool]$VerifiedBackend.launcherLeaseActive) {
                    throw "Another active launcher owns this Reporter Pro backend."
                }
            }

            $script:BackendIdentity = $VerifiedBackend
            Write-Step (
                "Backend instance $($VerifiedBackend.instanceId.Substring(0, 8)) " +
                "(PID $($VerifiedBackend.processId)) is verified and will be reused."
            )
            return $true
        }
    }

    $Listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $Listener) {
        return $false
    }

    foreach ($Item in $Listener) {
        $OwnerPid = $Item.OwningProcess
        if ($ServiceName -eq "backend") {
            throw "Port $Port is occupied by PID $OwnerPid, but it is not the verified Reporter Pro backend for this workspace."
        }

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

function Wait-ReporterBackendIdentity(
    [System.Diagnostics.Process]$Process,
    [string]$ExpectedWorkspace,
    [int]$TimeoutSeconds = 30
) {
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        if ($Process.HasExited) {
            throw "Backend PID $($Process.Id) exited before publishing its runtime identity."
        }
        $Identity = Get-ReporterBackendIdentity `
            "http://127.0.0.1:8000/api/health" `
            "http://127.0.0.1:8000/api/runtime/status" `
            $ExpectedWorkspace
        if ($Identity) {
            return $Identity
        }
        Start-Sleep -Milliseconds 300
    }
    throw "Timed out waiting for the Reporter Pro runtime identity."
}

function Get-HttpStatusCode($ErrorRecord) {
    try {
        return [int]$ErrorRecord.Exception.Response.StatusCode
    } catch {
        return 0
    }
}

function Stop-ExactProcess(
    [System.Diagnostics.Process]$Process,
    [string]$ServiceName
) {
    if (-not $Process) {
        return
    }
    try {
        if (-not $Process.HasExited) {
            Write-Step "Stopping $ServiceName PID $($Process.Id)..."
            Stop-Process -InputObject $Process -Force -ErrorAction Stop
            [void]$Process.WaitForExit(5000)
        }
    } catch {
        Write-Warning "Could not stop $ServiceName PID $($Process.Id): $($_.Exception.Message)"
    }
}

function Complete-BackendCleanup {
    if (-not $BackendProcess) {
        return
    }
    try {
        if ($BackendProcess.HasExited) {
            return
        }

        if ($LauncherAttached) {
            # The backend watchdog performs graceful shutdown after detach.
            if ($BackendProcess.WaitForExit(12000)) {
                return
            }
        }

        $CurrentIdentity = $null
        try {
            $CurrentIdentity = Get-ReporterBackendIdentity `
                "http://127.0.0.1:8000/api/health" `
                "http://127.0.0.1:8000/api/runtime/status" `
                $ExpectedWorkspaceFingerprint
        } catch {
            # A process handle created by this launcher still protects against
            # PID reuse even if HTTP is no longer available.
        }

        if (
            $CurrentIdentity -and
            $BackendIdentity -and
            $CurrentIdentity.instanceId -ne $BackendIdentity.instanceId
        ) {
            Write-Warning "Backend identity changed; cleanup will not stop the new instance."
            return
        }
        if ($CurrentIdentity -and [bool]$CurrentIdentity.launcherLeaseActive) {
            Write-Warning "Another launcher owns the backend; cleanup will leave it running."
            return
        }
        if ($CurrentIdentity -and [int]$CurrentIdentity.activeOperations -gt 0) {
            Write-Step "A report operation is still active; backend will stop automatically after it finishes."
            return
        }
        Stop-ExactProcess $BackendProcess "backend"
    } catch {
        Write-Warning "Could not complete backend cleanup: $($_.Exception.Message)"
    }
}

$ExpectedWorkspaceFingerprint = Get-WorkspaceFingerprint $Root

try {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor DarkCyan
    Write-Host " Reporter Pro - Application Launcher" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor DarkCyan
    Write-Host ""

    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

    $VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        throw "Backend environment is missing. Run setup.bat before starting Reporter Pro."
    }
    $Python = $VenvPython

    if ($Development) {
        $Node = Require-Command "node.exe"
        $ViteCli = Join-Path $FrontendDir "node_modules\vite\bin\vite.js"
        if (-not (Test-Path -LiteralPath $ViteCli)) {
            throw "Frontend dependencies are missing. Run setup.bat before development mode."
        }
        $AppUrl = "http://127.0.0.1:5173"
    } else {
        $FrontendIndex = Join-Path $FrontendDir "dist\index.html"
        if (-not (Test-Path -LiteralPath $FrontendIndex)) {
            throw "Frontend production build is missing. Run setup.bat or 'npm run build' in apps\frontend."
        }
        # A build-specific query prevents an already-open browser tab from
        # reusing a stale index.html after the production frontend changes.
        $BuildStamp = (Get-Item -LiteralPath $FrontendIndex).LastWriteTimeUtc.Ticks
        $AppUrl = "http://127.0.0.1:8000/?build=$BuildStamp"
    }

    $MutexName = "Local\ReporterPro-$ExpectedWorkspaceFingerprint"
    $CreatedMutex = $false
    $LauncherMutex = [System.Threading.Mutex]::new($false, $MutexName, [ref]$CreatedMutex)
    try {
        $MutexAcquired = $LauncherMutex.WaitOne(0)
    } catch [System.Threading.AbandonedMutexException] {
        $MutexAcquired = $true
        Write-Step "Recovered the launcher lock after an interrupted session."
    }

    if (-not $MutexAcquired) {
        Write-Step "Another launcher already manages this Reporter Pro workspace."
        $Deadline = (Get-Date).AddSeconds(30)
        while ((Get-Date) -lt $Deadline -and -not $BackendIdentity) {
            $BackendIdentity = Get-ReporterBackendIdentity `
                "http://127.0.0.1:8000/api/health" `
                "http://127.0.0.1:8000/api/runtime/status" `
                $ExpectedWorkspaceFingerprint
            if (-not $BackendIdentity) {
                Start-Sleep -Milliseconds 400
            }
        }
        if (-not $BackendIdentity) {
            throw "The active launcher did not make Reporter Pro ready within 30 seconds."
        }
        if (-not $NoBrowser) {
            Start-Process $AppUrl
            Write-Step "Opened the existing Reporter Pro instance."
        }
        return
    }

    $ReuseBackend = Resolve-ServicePort `
        8000 `
        "http://127.0.0.1:8000/api/health" `
        "backend" `
        "http://127.0.0.1:8000/api/runtime/status" `
        $ExpectedWorkspaceFingerprint

    $ReuseFrontend = $false
    if ($Development) {
        $ReuseFrontend = Resolve-ServicePort 5173 "http://127.0.0.1:5173" "frontend"
    }

    if (-not $ReuseBackend) {
        Write-Step "Starting backend..."
        # Run one uvicorn process so the launcher owns the actual listener PID.
        $BackendProcess = Start-Process -FilePath $Python `
            -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000" `
            -WorkingDirectory $BackendDir `
            -RedirectStandardOutput $BackendLog -RedirectStandardError "$BackendLog.err" `
            -PassThru -WindowStyle Hidden
        $StartedBackend = $true
        $BackendIdentity = Wait-ReporterBackendIdentity `
            $BackendProcess `
            $ExpectedWorkspaceFingerprint `
            30
        Write-Step (
            "Backend ready (PID $($BackendIdentity.processId), " +
            "instance $($BackendIdentity.instanceId.Substring(0, 8)))."
        )
    }

    if (-not $BackendIdentity) {
        throw "Reporter Pro backend identity was not established."
    }

    if (-not $Development) {
        $FrontendResponse = Invoke-WebRequest `
            -Uri "http://127.0.0.1:8000/" `
            -UseBasicParsing `
            -TimeoutSec 3
        if (
            $FrontendResponse.StatusCode -ne 200 -or
            $FrontendResponse.Content -notmatch "<title>Reporter Pro</title>"
        ) {
            throw "Backend is healthy but the Reporter Pro production interface is unavailable. Restart after rebuilding the frontend."
        }
    }

    if ($Development -and -not $ReuseFrontend) {
        Write-Step "Starting frontend..."
        $QuotedViteCli = '"' + $ViteCli + '"'
        $FrontendProcess = Start-Process -FilePath $Node `
            -ArgumentList $QuotedViteCli, "--host", "127.0.0.1", "--port", "5173", "--strictPort" `
            -WorkingDirectory $FrontendDir `
            -RedirectStandardOutput $FrontendLog -RedirectStandardError "$FrontendLog.err" `
            -PassThru -WindowStyle Hidden
        Wait-Http "http://127.0.0.1:5173" $FrontendProcess 45
        Write-Step "Frontend ready (PID $($FrontendProcess.Id))."
    }

    $LifecyclePayload = @{
        launcherId = $LauncherId
        pid = $PID
        instanceId = $BackendIdentity.instanceId
        workspaceFingerprint = $ExpectedWorkspaceFingerprint
    }
    try {
        [void](Invoke-Lifecycle "launcher/attach" $LifecyclePayload)
        $LauncherAttached = $true
        Write-Step "Exclusive launcher lease acquired; browser lifecycle is synchronized."
    } catch {
        if ((Get-HttpStatusCode $_) -eq 409) {
            $LauncherOwnershipLost = $true
            Write-Step "Reporter Pro is already managed by another active launcher."
            if (-not $NoBrowser) {
                Start-Process $AppUrl
                Write-Step "Opened the existing Reporter Pro instance."
            }
            return
        }
        throw
    }

    Write-Host ""
    $Mode = if ($Development) { "development" } else { "production" }
    Write-Host "Mode:     $Mode"
    Write-Host "App:      $AppUrl" -ForegroundColor Green
    Write-Host "API:      http://127.0.0.1:8000" -ForegroundColor Green
    Write-Host "API Docs: http://127.0.0.1:8000/docs" -ForegroundColor Green
    Write-Host "Instance: $($BackendIdentity.instanceId)"
    if ($StartedBackend) {
        Write-Host "Backend log: $BackendLog"
    }
    if ($Development -and $FrontendProcess) {
        Write-Host "Frontend log: $FrontendLog"
    }
    Write-Host ""

    if (-not $NoBrowser) {
        Start-Process $AppUrl
    }
    if ($ExitAfterReady) {
        Write-Step "Readiness check completed."
        return
    }
    Write-Host "Close the Reporter Pro browser tab or press ENTER to stop..."

    $HeartbeatFailures = 0
    while ($true) {
        $EnterPressed = $false
        try {
            if ([Console]::KeyAvailable) {
                $Key = [Console]::ReadKey($true)
                $EnterPressed = $Key.Key -eq [ConsoleKey]::Enter
            }
        } catch {
            # Non-interactive hosts may not expose a console input buffer.
        }
        if ($EnterPressed) {
            Write-Step "Stop requested from the launcher."
            break
        }

        try {
            $RuntimeStatus = Invoke-Lifecycle "launcher/heartbeat" $LifecyclePayload
            $HeartbeatFailures = 0
            if ($RuntimeStatus.shouldShutdown) {
                Write-Step "The last Reporter Pro browser tab was closed."
                break
            }
        } catch {
            if ((Get-HttpStatusCode $_) -eq 409) {
                $LauncherOwnershipLost = $true
                $LauncherAttached = $false
                Write-Warning "Launcher ownership was lost; this window will exit without stopping the backend."
                break
            }

            $HeartbeatFailures++
            $CurrentIdentity = Get-ReporterBackendIdentity `
                "http://127.0.0.1:8000/api/health" `
                "http://127.0.0.1:8000/api/runtime/status" `
                $ExpectedWorkspaceFingerprint
            if (
                $CurrentIdentity -and
                $CurrentIdentity.instanceId -ne $BackendIdentity.instanceId
            ) {
                throw "Reporter Pro backend restarted with a different instance identity."
            }
            if (-not $CurrentIdentity -and $HeartbeatFailures -ge 3) {
                throw "Reporter Pro backend stopped unexpectedly."
            }
            if ($HeartbeatFailures -eq 3) {
                Write-Warning "Backend is busy; launcher will wait without interrupting report work."
            }
        }
        Start-Sleep -Seconds 1
    }
} catch {
    Write-Host ""
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    if (Test-Path -LiteralPath $BackendLog) {
        Write-Host "Backend log: $BackendLog"
    }
    if (Test-Path -LiteralPath "$BackendLog.err") {
        Write-Host "Backend error log: $BackendLog.err"
    }
    if (Test-Path -LiteralPath $FrontendLog) {
        Write-Host "Frontend log: $FrontendLog"
    }
    if (Test-Path -LiteralPath "$FrontendLog.err") {
        Write-Host "Frontend error log: $FrontendLog.err"
    }
    exit 1
} finally {
    if ($LauncherAttached -and -not $LauncherOwnershipLost -and $LifecyclePayload) {
        try {
            [void](Invoke-Lifecycle "launcher/detach" $LifecyclePayload)
        } catch {
            # The backend may already be stopped.
        }
    }
    Stop-ExactProcess $FrontendProcess "frontend"
    Complete-BackendCleanup
    if ($LauncherMutex) {
        if ($MutexAcquired) {
            try {
                $LauncherMutex.ReleaseMutex()
            } catch {
                # The mutex may already have been abandoned during host teardown.
            }
        }
        $LauncherMutex.Dispose()
    }
}

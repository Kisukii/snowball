$ErrorActionPreference = 'Stop'

try {
    $snowballRoot = $PSScriptRoot
    $snowballPython = Join-Path $snowballRoot '.venv\Scripts\pythonw.exe'
    $snowballBackendPython = Join-Path $snowballRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $snowballPython)) {
        throw 'Run start_desktop.bat once to install Snow Ball.'
    }
    $snowballLogs = Join-Path $snowballRoot '.runtime'
    New-Item -ItemType Directory -Path $snowballLogs -Force | Out-Null
    try {
        $snowballHealth = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2
    } catch {
        $snowballHealth = $null
    }
    if ($snowballHealth -and ($snowballHealth.capabilities -notcontains 'desktop-interface' -or $snowballHealth.capabilities -notcontains 'malayalam-voice')) {
        $snowballOldBackend = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
            Where-Object {
                $_.CommandLine -like '*-m uvicorn backend.main:app*' -and
                $_.CommandLine.Contains($snowballRoot + '\.venv\Scripts\')
            }
        if (-not $snowballOldBackend) {
            throw 'Port 8000 is occupied by another backend. Close it before opening Snow Ball.'
        }
        foreach ($snowballProcess in $snowballOldBackend) {
            Stop-Process -Id $snowballProcess.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 500
        $snowballHealth = $null
    }
    if (-not $snowballHealth) {
        Start-Process -FilePath $snowballBackendPython -ArgumentList '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $snowballRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $snowballLogs 'backend-out.log') -RedirectStandardError (Join-Path $snowballLogs 'backend-error.log')
        for ($snowballAttempt = 0; $snowballAttempt -lt 12; $snowballAttempt++) {
            Start-Sleep -Milliseconds 500
            try {
                $snowballHealth = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 1
                break
            } catch {}
        }
        if (-not $snowballHealth) { throw 'The backend could not start. See .runtime\backend-error.log.' }
    }
    if ($snowballHealth.status -ne 'ok' -or $snowballHealth.capabilities -notcontains 'malayalam-voice') {
        throw 'Stop the old backend on port 8000, then launch Snow Ball again.'
    }
    # Only restart this checkout's desktop companion.
    $snowballProcesses = Get-CimInstance Win32_Process -Filter "name = 'python.exe' OR name = 'pythonw.exe'" |
        Where-Object {
            $_.CommandLine -match '-m\s+desktop\.app(?:\s|$)' -and
            $_.CommandLine.Contains($snowballRoot + '\.venv\Scripts\')
        }
    foreach ($snowballProcess in $snowballProcesses) {
        Stop-Process -Id $snowballProcess.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if ($snowballProcesses) { Start-Sleep -Milliseconds 500 }
    Start-Process -FilePath $snowballPython -ArgumentList '-m','desktop.app' -WorkingDirectory $snowballRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $snowballLogs 'desktop-out.log') -RedirectStandardError (Join-Path $snowballLogs 'desktop-error.log')
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Snow Ball') | Out-Null
}


$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$snowballPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $snowballPython)) {
    throw 'Run start_desktop.bat first to create the Snowball environment.'
}
try {
    Invoke-WebRequest 'http://127.0.0.1:8000/health' -TimeoutSec 2 -UseBasicParsing | Out-Null
    $snowballBackendRunning = $true
} catch {
    $snowballBackendRunning = $false
}
if ($snowballBackendRunning) {
    throw 'A backend is already running on port 8000. Stop it in its terminal (Ctrl+C), then run this launcher again.'
}
& $snowballPython -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install backend dependencies.' }
if (-not $env:GEMINI_API_KEY) {
    $snowballSecret = Read-Host 'Paste your Gemini API key (hidden)' -AsSecureString
    $snowballPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($snowballSecret)
    try {
        $env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($snowballPointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($snowballPointer)
        $snowballSecret.Dispose()
    }
}
if ([string]::IsNullOrWhiteSpace($env:GEMINI_API_KEY)) { throw 'An API key is required.' }
$env:PAWLY_MODE = 'gemini'
Write-Host 'Starting Gemini guidance. Keep this window open; press Ctrl+C to stop.'
try {
    & $snowballPython -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
} finally {
    Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
}

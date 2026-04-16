# Restart FPNA Backend - stop listener on port 8001, then start uvicorn (same as start-backend.ps1)
param(
    [int] $Port = 8001
)

$ErrorActionPreference = 'Continue'

Write-Host ('Stopping process(es) listening on port {0} ...' -f $Port)
try {
    $conns = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    $seen = @{}
    foreach ($c in $conns) {
        $procId = $c.OwningProcess
        if ($seen.ContainsKey($procId)) { continue }
        $seen[$procId] = $true
        try {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                Stop-Process -Id $procId -Force -ErrorAction Stop
                Write-Host ('  Stopped PID {0} ({1})' -f $procId, $proc.ProcessName)
            }
        } catch {
            Write-Host ('  Could not stop PID {0}: {1}' -f $procId, $_)
        }
    }
    if (-not $conns) {
        Write-Host ('  (nothing was listening on {0})' -f $Port)
    }
} catch {
    Write-Host ('  Note: could not query connections (try closing the old terminal or Task Manager). {0}' -f $_)
}

Start-Sleep -Seconds 1

$backend = Join-Path $PSScriptRoot 'backend'
Set-Location $backend

$venvActivate = Join-Path $backend '.venv\Scripts\Activate.ps1'
if (-not (Test-Path $venvActivate)) {
    Write-Error 'Virtual env not found at backend\.venv - create it and install requirements first.'
    exit 1
}

Write-Host 'Activating virtual environment...'
& $venvActivate
Write-Host ('Starting backend on http://127.0.0.1:{0} ...' -f $Port)
python -m uvicorn app.main:app --host 127.0.0.1 --port $Port

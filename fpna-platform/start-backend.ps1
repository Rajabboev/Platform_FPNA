# Start FPNA Backend
Set-Location $PSScriptRoot\backend
Write-Host "Starting backend on http://127.0.0.1:8001 ..."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

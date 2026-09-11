$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Iniciando API em http://127.0.0.1:8000"
Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload" -WorkingDirectory $root -WindowStyle Hidden

Write-Host "Iniciando dashboard em http://localhost:5173"
Set-Location (Join-Path $root "frontend")
npm.cmd run dev

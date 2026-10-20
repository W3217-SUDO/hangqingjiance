$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Missing .venv. See README.zh-CN.md for setup.' }
New-Item -ItemType Directory -Path (Join-Path $projectPath 'logs') -Force | Out-Null
try {
    $running = Invoke-RestMethod 'http://127.0.0.1:8010/api/hedge/integrations' -TimeoutSec 2
    if ($running.plan -eq 'free') { Write-Output 'Crossmarket Pulse is already running: http://127.0.0.1:8010'; exit 0 }
} catch { }
$serviceProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','src.market_stream.app:app','--host','127.0.0.1','--port','8010') -WorkingDirectory $projectPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectPath 'logs/server.log') -RedirectStandardError (Join-Path $projectPath 'logs/server-error.log') -PassThru
Set-Content -LiteralPath (Join-Path $projectPath 'logs/service.pid') -Value $serviceProcess.Id
Write-Output "Started Crossmarket Pulse (PID $($serviceProcess.Id)): http://127.0.0.1:8010"

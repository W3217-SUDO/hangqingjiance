$ErrorActionPreference = 'Stop'
$pidPath = Join-Path $PSScriptRoot 'logs/service.pid'
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Output 'No managed service PID found.'; exit 0 }
$servicePid = [int](Get-Content -LiteralPath $pidPath)
$serviceProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $servicePid" -ErrorAction SilentlyContinue
if ($serviceProcess -and $serviceProcess.CommandLine -like '*src.market_stream.app:app*' -and $serviceProcess.CommandLine -like '*8010*') {
    Get-CimInstance Win32_Process -Filter "ParentProcessId = $servicePid" | Where-Object { $_.CommandLine -like '*src.market_stream.app:app*' -and $_.CommandLine -like '*8010*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
    Stop-Process -Id $servicePid
    Write-Output 'Stopped Crossmarket Pulse.'
} else { Write-Output 'PID no longer matches the managed service; nothing stopped.' }

@echo off
setlocal EnableExtensions

rem Stop api_v2 (9880) and the relay (9881) started by start-all.bat.
rem Works by port, so it also cleans up windows whose title was changed.

echo Stopping processes listening on 9880 / 9881 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach($p in 9880,9881){$pids=Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; foreach($procId in $pids){try{Stop-Process -Id $procId -Force -ErrorAction Stop; Write-Host ('  killed PID ' + $procId + ' on port ' + $p)}catch{Write-Host ('  cannot kill PID ' + $procId + ': ' + $_.Exception.Message)}}}"

rem Fallback: kill by window title
taskkill /FI "WINDOWTITLE eq GPT-SoVITS API*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq GPT-SoVITS Relay*" /T /F >nul 2>&1

echo Done. If a black window is still open, close it manually.
ping -n 4 127.0.0.1 >nul
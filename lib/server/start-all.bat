@echo off
setlocal EnableExtensions

rem One-click launcher for the SillyTavern GPT-SoVITS plugin.
rem   - starts api_v2 on 9880
rem   - waits until it answers
rem   - starts the CORS relay on 9881
rem To use another install, create gsv-dir.txt next to this bat with one line:
rem   E:\path\to\GPT-SoVITS

set "HERE=%~dp0"
set "GSV=E:\GPT-SoVITS-v5-20261005\GPT-SoVITS-v2pro-20261006"
if exist "%HERE%gsv-dir.txt" set /p GSV=<"%HERE%gsv-dir.txt"
set "API_PORT=9880"
set "RELAY_PORT=9881"

if not exist "%GSV%\runtime\python.exe" (
    echo [ERROR] python not found: %GSV%\runtime\python.exe
    echo         Put the GPT-SoVITS path into gsv-dir.txt next to this bat.
    pause
    exit /b 1
)
if not exist "%GSV%\GPT_SoVITS\configs\tts_infer_v2pro.yaml" (
    echo [ERROR] config not found: %GSV%\GPT_SoVITS\configs\tts_infer_v2pro.yaml
    pause
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if not exist "%TEMP%\gsv-mpl" mkdir "%TEMP%\gsv-mpl"
set "MPLCONFIGDIR=%TEMP%\gsv-mpl"

echo Starting api_v2 on port %API_PORT% ...
start "GPT-SoVITS API" /D "%GSV%" "%GSV%\runtime\python.exe" api_v2.py -a 127.0.0.1 -p %API_PORT% -c GPT_SoVITS/configs/tts_infer_v2pro.yaml

echo Waiting for api_v2 (first model load takes 1-3 minutes) ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "for($i=0;$i -lt 100;$i++){try{Invoke-WebRequest ('http://127.0.0.1:%API_PORT%/control') -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop|Out-Null;exit 0}catch{if($_.Exception.Response){exit 0};Start-Sleep -Seconds 3}};exit 1"
if errorlevel 1 (
    echo [WARN] api_v2 is not ready yet. The relay returns 502 until it is.
) else (
    echo api_v2 is ready.
)

echo Starting relay on port %RELAY_PORT% ...
start "GPT-SoVITS Relay" /D "%HERE%" "%GSV%\runtime\python.exe" gptsovits_relay.py --port %RELAY_PORT% --upstream 127.0.0.1:%API_PORT%

echo.
echo   api_v2 : http://127.0.0.1:%API_PORT%
echo   relay  : http://127.0.0.1:%RELAY_PORT%    ^<-- use this in the plugin
echo.
echo   Two windows were opened. Close them or run stop-all.bat to stop.
ping -n 8 127.0.0.1 >nul
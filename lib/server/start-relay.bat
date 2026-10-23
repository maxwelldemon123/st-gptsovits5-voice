@echo off
setlocal EnableExtensions

rem GPT-SoVITS CORS relay: 9881 -> 9880
rem Edit UPSTREAM if GPT-SoVITS runs on another machine.

set "UPSTREAM=127.0.0.1:9880"
set "PORT=9881"
rem If you use a uv/venv install, point PYTHON to its python.exe
set "PYTHON=python"

cd /d "%~dp0"
echo.
echo   GPT-SoVITS relay
echo   upstream : %UPSTREAM%
echo   listen   : http://127.0.0.1:%PORT%
echo   In the tavern plugin, use http://127.0.0.1:%PORT%
echo.

"%PYTHON%" gptsovits_relay.py --port %PORT% --upstream %UPSTREAM%

echo.
echo [exited] press any key to close
pause >nul
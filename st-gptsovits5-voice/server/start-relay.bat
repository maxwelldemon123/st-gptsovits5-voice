@echo off
chcp 65001 >nul
setlocal

rem ============================================================
rem  GPT-SoVITS 中继（补 CORS）
rem  GPT-SoVITS 跑在别的机器上就改 UPSTREAM
rem ============================================================

set "UPSTREAM=127.0.0.1:9880"
set "PORT=9881"
rem 用 uv 虚拟环境的话，指向它的 python.exe
set "PYTHON=python"

cd /d "%~dp0"
echo.
echo   GPT-SoVITS 中继
echo   上游 : %UPSTREAM%
echo   监听 : http://127.0.0.1:%PORT%
echo.
echo   酒馆插件里的地址填 http://127.0.0.1:%PORT%
echo   关闭这个窗口 = 停止中继
echo.

"%PYTHON%" gptsovits_relay.py --port %PORT% --upstream %UPSTREAM%

echo.
echo [中继已退出] 按任意键关闭
pause >nul

@echo off
setlocal
cd /d "%~dp0"
echo AI Daytrade Pro V1.07.1 - private live signal launcher
echo Market data and iPhone push use require Fugle authorization.
echo This tool never places orders.
py -m v1071.launch_live_windows
echo.
echo Launcher exited. Press any key to close.
pause >nul

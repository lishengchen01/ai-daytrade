@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo AI Daytrade Pro V1.08 - Windows shadow scanner installer
echo This is RESEARCH ONLY. It will NOT send live signals or place orders.
py -m v108.install_shadow
echo.
echo Installation command finished. See the message above for its actual result.
pause

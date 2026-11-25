@echo off
setlocal
cd /d "%~dp0"
echo.
echo AI Daytrade Pro V1.07.2 - One-time background push installer
echo Only TEST push; no Fugle market feed and no trading signal.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL-PRIVATE-PUSH-BACKGROUND.ps1"
if errorlevel 1 (
  echo.
  echo Installation did not complete. Existing service remains unchanged.
) else (
  echo.
  echo Registration complete. Read the instructions above before switching.
)
echo.
pause

@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" -UsePrebuiltFrontend %*
if errorlevel 1 (
  echo.
  echo Reporter Pro prebuilt setup failed. Review the error above.
  pause
  exit /b 1
)
echo.
echo Setup completed. Run start.bat to launch Reporter Pro.
pause

@echo off
setlocal
chcp 65001 >nul
title Reporter Pro

set "SCRIPT=%~dp0scripts\start-reporter.ps1"
if not exist "%SCRIPT%" (
  echo [ERROR] Missing launcher: %SCRIPT%
  exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Reporter Pro could not start. Review the error above, then press any key.
  pause >nul
)
exit /b %EXIT_CODE%

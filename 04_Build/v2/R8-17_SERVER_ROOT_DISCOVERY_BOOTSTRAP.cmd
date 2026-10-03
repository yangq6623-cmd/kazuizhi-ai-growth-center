@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0R8-17_SERVER_ROOT_DISCOVERY_BOOTSTRAP.ps1"
exit /b %ERRORLEVEL%

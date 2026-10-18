@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0R8-15_SERVER_BOOTSTRAP.ps1"
exit /b %ERRORLEVEL%

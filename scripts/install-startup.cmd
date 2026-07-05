@echo off
title Install Yuzhuan Startup
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-startup.ps1"
echo.
pause

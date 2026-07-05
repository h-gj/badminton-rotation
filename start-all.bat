@echo off
cd /d "%~dp0"
start "Yuzhuan Django" cmd /k scripts\run-production.cmd
timeout /t 15 /nobreak >nul
start "Yuzhuan Tunnel" cmd /k scripts\run-tunnel.cmd

@echo off
title Yuzhuan Tunnel
cd /d "%~dp0.."

echo ========================================
echo   Yuzhuan Cloudflare Tunnel
echo ========================================
echo.

where cloudflared >nul 2>&1
if errorlevel 1 (
    echo [ERROR] cloudflared not installed
    echo Run: winget install Cloudflare.cloudflared
    goto END
)

if not exist "%USERPROFILE%\.cloudflared\config.yml" (
    echo [ERROR] missing config.yml
    echo Copy deploy\cloudflared-config.example.yml to:
    echo   %USERPROFILE%\.cloudflared\config.yml
    goto END
)

echo Starting tunnel... Press Ctrl+C to stop
echo.

cloudflared tunnel run badminton-rotation
echo.
echo Tunnel stopped

:END
echo.
pause

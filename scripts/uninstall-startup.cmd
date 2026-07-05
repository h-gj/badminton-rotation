@echo off
title Uninstall Yuzhuan Startup

set "LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Yuzhuan Badminton.lnk"

echo ========================================
echo   Remove login startup shortcut
echo ========================================
echo.

if exist "%LINK%" (
    del "%LINK%"
    echo [OK] Removed: %LINK%
) else (
    echo [INFO] Shortcut not found, nothing to remove.
)

echo.
pause

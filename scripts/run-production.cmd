@echo off
title Yuzhuan Django
cd /d "%~dp0.."

echo ========================================
echo   Yuzhuan Django (production)
echo ========================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found. Run: python -m venv venv
    goto END
)

call venv\Scripts\activate.bat

echo [1/4] pip install...
venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 goto FAIL

echo [2/4] migrate...
venv\Scripts\python.exe manage.py migrate --noinput
if errorlevel 1 goto FAIL

echo [3/4] collectstatic...
venv\Scripts\python.exe manage.py collectstatic --noinput
if errorlevel 1 goto FAIL

if not exist "venv\Scripts\waitress-serve.exe" (
    echo [ERROR] waitress not found
    goto FAIL
)

echo [4/4] starting waitress on http://127.0.0.1:8000
echo Also run scripts\run-tunnel.cmd in another window
echo Press Ctrl+C to stop
echo.

venv\Scripts\waitress-serve.exe --listen=127.0.0.1:8000 config.wsgi:application
echo.
echo Server stopped
goto END

:FAIL
echo.
echo [FAILED] see errors above

:END
echo.
pause

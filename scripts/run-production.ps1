# 在本机以生产模式启动 Django（配合 Cloudflare Tunnel 使用）
# 用法（任选其一）：
#   scripts\run-production.cmd
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-production.ps1

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path '.\venv\Scripts\Activate.ps1')) {
    Write-Error '未找到 venv，请先运行: python -m venv venv'
}

& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt -q
python manage.py migrate --noinput
python manage.py collectstatic --noinput

Write-Host ''
Write-Host 'Django 生产服务启动于 http://127.0.0.1:8000' -ForegroundColor Green
Write-Host '请另开终端运行: cloudflared tunnel run badminton-rotation' -ForegroundColor Yellow
Write-Host ''

& .\venv\Scripts\waitress-serve.exe --listen=127.0.0.1:8000 config.wsgi:application

# 启动 Cloudflare Tunnel（需先配置 %USERPROFILE%\.cloudflared\config.yml）
# 用法（任选其一）：
#   scripts\run-tunnel.cmd
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-tunnel.ps1

$ErrorActionPreference = 'Stop'

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Error '未安装 cloudflared，请运行: winget install Cloudflare.cloudflared'
}

$config = Join-Path $env:USERPROFILE '.cloudflared\config.yml'
if (-not (Test-Path $config)) {
    Write-Error "未找到配置文件: $config`n请参考 deploy/cloudflared-config.example.yml 创建"
}

Write-Host '启动 Cloudflare Tunnel...' -ForegroundColor Green
cloudflared tunnel run badminton-rotation

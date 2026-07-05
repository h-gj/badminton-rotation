$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LinkPath = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\Yuzhuan Badminton.lnk'

Write-Host '========================================'
Write-Host '  Install login startup shortcut'
Write-Host '========================================'
Write-Host ''
Write-Host "Project: $ProjectRoot"
Write-Host "Link:    $LinkPath"
Write-Host ''

$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut($LinkPath)
$shortcut.TargetPath = Join-Path $ProjectRoot 'start-all.bat'
$shortcut.WorkingDirectory = $ProjectRoot
$shortcut.Description = 'Yuzhuan Django + Cloudflare Tunnel'
$shortcut.Save()

if (Test-Path $LinkPath) {
    Write-Host '[OK] Shortcut created.'
    Write-Host 'Yuzhuan will start automatically on next login.'
    Write-Host 'To remove: run scripts\uninstall-startup.cmd'
} else {
    Write-Host '[FAILED] shortcut was not created'
    exit 1
}

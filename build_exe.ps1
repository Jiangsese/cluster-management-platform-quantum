$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppName = "量子集群服务器控制台"
$Python = $env:PYTHON
if (-not $Python) {
  $Python = Join-Path $Root ".venv\Scripts\python.exe"
}
if ($Python -ne "python" -and -not (Test-Path -LiteralPath $Python)) {
  $Python = "python"
}
Set-Location $Root
& $Python -m PyInstaller `
  --noconfirm `
  --clean `
  --noconsole `
  --name "$AppName" `
  --icon "$Root\assets\quantum-icon.ico" `
  --add-data "assets;assets" `
  --paths "$Root" `
  "$Root\native_app.py"
Write-Host "Built: $Root\dist\$AppName\$AppName.exe"

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = $env:PYTHON
if (-not $Python) {
  $Python = Join-Path $Root ".venv\Scripts\python.exe"
}
if ($Python -ne "python" -and -not (Test-Path -LiteralPath $Python)) {
  $Python = "python"
}
& $Python "$Root\native_app.py"

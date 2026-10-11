# claude-kit installer (Windows PowerShell). Arguments pass through, e.g. -- --with-claude-mem, --uninstall.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$py = Get-Command python, py -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $py) { Write-Error 'Python 3.10+ is required'; exit 1 }
& $py.Source scripts/install.py @args
exit $LASTEXITCODE

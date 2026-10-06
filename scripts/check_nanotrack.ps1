param(
    [string]$ReportDir,
    [string]$CondaExe,
    [switch]$RuntimeSmoke
)

$gateArgs = @()
if ($ReportDir) { $gateArgs += @('--report-dir', $ReportDir) }
if ($RuntimeSmoke) { $gateArgs += '--runtime-smoke' }
$launcherArgs = @()
if ($CondaExe) { $launcherArgs += @('-CondaExe', $CondaExe) }
$launcherArgs += @('-ScriptPath', 'scripts/check_nanotrack.py') + $gateArgs
& (Join-Path $PSScriptRoot 'run_python_utf8.ps1') @launcherArgs
exit $LASTEXITCODE

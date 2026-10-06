# Start with legacy settings and capture native output as PowerShell strings.
param([string]$Launcher, [string]$PythonExe, [string]$Probe, [int]$ExitCode = 0)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.Encoding]::ASCII
[Console]::InputEncoding = [Text.Encoding]::ASCII
[Console]::OutputEncoding = [Text.Encoding]::ASCII
$env:PYTHONUTF8 = '0'
$env:PYTHONIOENCODING = 'ascii'
$beforeLocation = (Get-Location).Path
$result = & $Launcher -PythonExe $PythonExe -ScriptPath $Probe $ExitCode
$childExit = $LASTEXITCODE
if ($childExit -ne $ExitCode) { exit 40 }
if ($env:PYTHONUTF8 -ne '0' -or $env:PYTHONIOENCODING -ne 'ascii') { exit 41 }
if ([Console]::InputEncoding.CodePage -ne 20127 -or [Console]::OutputEncoding.CodePage -ne 20127) { exit 42 }
if ($OutputEncoding.CodePage -ne 20127 -or (Get-Location).Path -ne $beforeLocation) { exit 43 }
# Verify PowerShell decoded the native UTF-8 output before restoring its settings.
$payload = $result | ConvertFrom-Json
if ($payload.message -notmatch ([char]0x17c)) { exit 44 }
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$result
exit $childExit

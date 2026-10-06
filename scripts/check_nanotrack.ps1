param(
    [string]$ReportDir,
    [string]$CondaExe,
    [switch]$RuntimeSmoke
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $CondaExe) {
    $condaCommand = Get-Command conda.exe -ErrorAction SilentlyContinue
    $candidates = @(
        $env:CONDA_EXE
        $(if ($condaCommand) { $condaCommand.Source })
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe"
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe"
        "$env:USERPROFILE\miniforge3\Scripts\conda.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            $CondaExe = $candidate
            break
        }
    }
}
if (-not $CondaExe -or -not (Test-Path -LiteralPath $CondaExe -PathType Leaf)) {
    throw 'Conda executable not found. Set CONDA_EXE or pass -CondaExe with its full path.'
}

$gateArgs = @('run', '--no-capture-output', '-n', 'netcat', 'python', 'scripts/check_nanotrack.py')
if ($ReportDir) { $gateArgs += @('--report-dir', $ReportDir) }
if ($RuntimeSmoke) { $gateArgs += '--runtime-smoke' }
Push-Location -LiteralPath $repoRoot
try {
    Write-Host "Conda: $CondaExe"
    & $CondaExe @gateArgs
    $gateExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $gateExitCode

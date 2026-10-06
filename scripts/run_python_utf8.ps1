# Keep this bootstrap ASCII so Windows PowerShell 5.1 can read it without a BOM.
# Parse launcher options ourselves: PowerShell's parameter binder otherwise
# consumes Python options such as -p (as an abbreviation of -PythonExe).
# Put launcher options first; everything after the target is passed unchanged.

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$previousInputEncoding = [Console]::InputEncoding
$previousOutputEncoding = [Console]::OutputEncoding
$previousPythonUtf8 = $env:PYTHONUTF8
$previousPythonIoEncoding = $env:PYTHONIOENCODING
$locationPushed = $false
$commandExitCode = 1

try {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $OutputEncoding = $utf8
    [Console]::InputEncoding = $utf8
    [Console]::OutputEncoding = $utf8
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    Push-Location -LiteralPath $repoRoot
    $locationPushed = $true

    $PythonExe = $null
    $CondaExe = $null
    $CondaEnv = 'netcat'
    $ScriptPath = $null
    $Module = $null
    $Arguments = @()
    for ($index = 0; $index -lt $args.Count; $index++) {
        $option = [string]$args[$index]
        if ($option -in @('-PythonExe', '-CondaExe', '-CondaEnv', '-ScriptPath', '-Module')) {
            if ($index + 1 -ge $args.Count) { throw "Missing value for $option." }
            $index++
            $value = [string]$args[$index]
            switch ($option) {
                '-PythonExe' { $PythonExe = $value }
                '-CondaExe' { $CondaExe = $value }
                '-CondaEnv' { $CondaEnv = $value }
                '-ScriptPath' { $ScriptPath = $value }
                '-Module' { $Module = $value }
            }
            if ($option -in @('-ScriptPath', '-Module')) { break }
        } elseif (-not $option.StartsWith('-')) {
            $ScriptPath = $option
            break
        } else {
            throw "Unknown launcher option: $option. Select a .py file or -Module before Python arguments."
        }
    }
    if ($index + 1 -lt $args.Count) { $Arguments = @($args[($index + 1)..($args.Count - 1)]) }
    if ($Arguments.Count -gt 0 -and $Arguments[0] -eq '--') { $Arguments = @($Arguments | Select-Object -Skip 1) }
    if (-not $ScriptPath -and -not $Module) { throw 'Select an existing .py file or -Module name.' }
    if ($ScriptPath) {
        if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf) -or [IO.Path]::GetExtension($ScriptPath) -ne '.py') {
            throw 'ScriptPath must name an existing .py file; save Python code as UTF-8 instead of using -c or stdin.'
        }
        $target = @((Resolve-Path -LiteralPath $ScriptPath).ProviderPath)
    } else {
        if ($Module -notmatch '^[A-Za-z_][A-Za-z_0-9]*(\.[A-Za-z_][A-Za-z_0-9]*)*$') {
            throw 'Module must be a Python module name, such as pytest or unittest.'
        }
        $target = @('-m', $Module)
    }
    $pythonArgs = @('-X', 'utf8') + $target + $Arguments

    if ($PythonExe) {
        if ($CondaExe) { throw 'Choose either PythonExe or CondaExe.' }
        if (Test-Path -LiteralPath $PythonExe -PathType Leaf) {
            $command = (Resolve-Path -LiteralPath $PythonExe).ProviderPath
        } else {
            $command = (Get-Command -Name $PythonExe -CommandType Application -ErrorAction Stop).Source
        }
        $commandArgs = $pythonArgs
    } else {
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
            throw 'Conda executable not found. Set CONDA_EXE, pass -CondaExe or select -PythonExe.'
        }
        $command = (Resolve-Path -LiteralPath $CondaExe).ProviderPath
        $commandArgs = @('run', '--no-capture-output', '-n', $CondaEnv, 'python') + $pythonArgs
    }

    # Native stderr is not a PowerShell exception; the child's exit code wins.
    $ErrorActionPreference = 'Continue'
    $PSNativeCommandUseErrorActionPreference = $false
    $global:LASTEXITCODE = 1
    & $command @commandArgs
    $commandExitCode = $global:LASTEXITCODE
} catch {
    [Console]::Error.WriteLine("UTF-8 launcher: " + $_.Exception.Message)
} finally {
    if ($locationPushed) { Pop-Location }
    [Environment]::SetEnvironmentVariable('PYTHONUTF8', $previousPythonUtf8, 'Process')
    [Environment]::SetEnvironmentVariable('PYTHONIOENCODING', $previousPythonIoEncoding, 'Process')
    [Console]::InputEncoding = $previousInputEncoding
    [Console]::OutputEncoding = $previousOutputEncoding
}
exit $commandExitCode

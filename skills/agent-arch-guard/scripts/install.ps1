<#
.SYNOPSIS
    ArchGuard installer (Python-backed wrapper; qoder / dsh / codex).
.DESCRIPTION
    Thin PowerShell wrapper around scripts/install.py, matching this repo's
    install.ps1 convention. All real logic lives in Python; this script only
    locates a Python 3.9+ interpreter and forwards arguments verbatim.
.PARAMETER Project
    Target project root. Defaults to current directory.
.PARAMETER Harness
    auto (default) | all | qoder | dsh | codex
.PARAMETER DryRun
    Print actions only; write nothing.
.PARAMETER Force
    Overwrite even when content is identical.
.PARAMETER UserLevel
    Install to user-level dirs (dsh / codex only).
.PARAMETER WithHook
    Install the git pre-commit hook.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Project d:\workspaces\ai\srm -Harness all
.EXAMPLE
    .\install.ps1 -Project . -Harness qoder -DryRun
.NOTES
    Requires Python 3.9+ as py -3, python, or python3.
    Output stays ASCII to avoid Windows PowerShell 5.1 codepage issues.
#>
[CmdletBinding()]
param(
    [string]$Project = '.',
    [ValidateSet('auto', 'all', 'qoder', 'dsh', 'codex')]
    [string]$Harness = 'auto',
    [switch]$DryRun,
    [switch]$Force,
    [switch]$UserLevel,
    [switch]$WithHook
)

$ErrorActionPreference = 'Stop'

$Installer = Join-Path $PSScriptRoot 'install.py'
if (-not (Test-Path $Installer)) {
    Write-Error "install.py not found next to this script: $Installer"
    exit 1
}

function Resolve-PythonCommand {
    $candidates = @(
        @('py', '-3'),
        @('python'),
        @('python3')
    )
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $prefix = @($candidate | Select-Object -Skip 1)
        $probe = @($prefix + @('-c', "import sys; print('%d.%d' % sys.version_info[:2])"))
        try {
            $version = & $exe @probe 2>$null
            if ($LASTEXITCODE -ne 0 -or -not $version) { continue }
            $match = [regex]::Match(($version | Out-String).Trim(), '^(\d+)\.(\d+)$')
            if (-not $match.Success) { continue }
            $major = [int]$match.Groups[1].Value
            $minor = [int]$match.Groups[2].Value
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 9)) {
                return @{ Exe = $exe; Prefix = $prefix }
            }
        } catch { }
    }
    return $null
}

$python = Resolve-PythonCommand
if ($null -eq $python) {
    Write-Error 'Python 3.9+ not found on PATH (tried: py -3, python, python3).'
    exit 1
}

$pyArgs = @($python.Prefix) + @('-I', $Installer, '--project', $Project, '--harness', $Harness)
if ($DryRun)    { $pyArgs += '--dry-run' }
if ($Force)     { $pyArgs += '--force' }
if ($UserLevel) { $pyArgs += '--user-level' }
if ($WithHook)  { $pyArgs += '--with-hook' }

& $python.Exe @pyArgs
exit $LASTEXITCODE

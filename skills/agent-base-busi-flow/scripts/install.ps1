<#
.SYNOPSIS
    BizFlow-8 (agent-base-busi-flow) project-level installer.
.DESCRIPTION
    Copies skills/busi-*/ to <TargetProject>/.qoder/skills/ so Qoder can auto-discover and trigger them.
    Idempotent: by default only newer files are copied (robocopy /XO). Use -Force to overwrite all.
    After copying, checks .agent/ overlay files (AGENT.md, coding-rules.md, overlay-spec.md).
    If any are missing, prints a prominent reminder to trigger busi-project-init skill.
    Use -InitOverlay to scaffold template overlay files directly (non-interactive, all TODO markers).
.PARAMETER TargetProject
    Target business service project root (required). e.g. d:\workspaces\ai\ocs
.PARAMETER Force
    Force overwrite existing SKILL.md (default: only copy newer)
.PARAMETER InitOverlay
    Scaffold .agent/ overlay template files from busi-project-init/references/ (non-interactive)
.PARAMETER DryRun
    Print actions only, do not execute
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install.ps1 -TargetProject d:\workspaces\ai\ocs
.EXAMPLE
    .\install.ps1 -TargetProject d:\workspaces\ai\ocs -Force
.EXAMPLE
    .\install.ps1 -TargetProject d:\workspaces\ai\ocs -InitOverlay
.NOTES
    Requires PowerShell 5+ / Windows 10+
    Script parent dir is treated as repo root (containing skills/, rules/, templates/)
    All output is ASCII-safe to avoid Windows PowerShell 5.1 GB18030 parsing issues.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetProject,

    [switch]$Force,

    [switch]$InitOverlay,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# ---------- 1. Resolve and validate paths ----------
$RepoRoot  = Split-Path -Parent $PSScriptRoot
$SkillsSrc = Join-Path $RepoRoot 'skills'

if (-not (Test-Path $SkillsSrc)) {
    Write-Error "Source skills/ dir not found: $SkillsSrc"
    exit 1
}
if (-not (Test-Path $TargetProject)) {
    Write-Error "Target project dir not found: $TargetProject"
    exit 1
}

$TargetProject = (Resolve-Path $TargetProject).Path
$SkillsDst     = Join-Path $TargetProject '.qoder\skills'

Write-Host ""
Write-Host "==== BizFlow-8 Install ====" -ForegroundColor Cyan
Write-Host "  Source : $SkillsSrc"
Write-Host "  Target : $SkillsDst"
$mode = if ($Force) { 'Force overwrite' } else { 'Incremental (skip older)' }
Write-Host "  Mode   : $mode"
if ($InitOverlay) { Write-Host "  Init   : Overlay scaffolding ON" -ForegroundColor Yellow }
if ($DryRun) { Write-Host "  DryRun : ON" -ForegroundColor Yellow }
Write-Host ""

# ---------- 2. Enumerate busi-* skills ----------
$SkillDirs = Get-ChildItem -Path $SkillsSrc -Directory | Where-Object { $_.Name -like 'busi-*' }
if ($SkillDirs.Count -eq 0) {
    Write-Error "No skills/busi-* directories found"
    exit 1
}
Write-Host "[1/5] Found $($SkillDirs.Count) BizFlow-8 skills:" -ForegroundColor Green
foreach ($d in $SkillDirs) { Write-Host "      - $($d.Name)" }
Write-Host ""

# ---------- 3. Check target .agent/ overlay (per-file) ----------
$AgentOverlay = Join-Path $TargetProject '.agent'
$OverlayFiles = @('AGENT.md', 'coding-rules.md', 'overlay-spec.md')
$MissingFiles = @()

Write-Host "[2/5] Verify target overlay:" -ForegroundColor Green
foreach ($f in $OverlayFiles) {
    $fpath = Join-Path $AgentOverlay $f
    if (Test-Path $fpath) {
        Write-Host "      [OK]   .agent\$f"
    } else {
        Write-Host "      [MISS] .agent\$f" -ForegroundColor Yellow
        $MissingFiles += $f
    }
}
if ($MissingFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "      -> $($MissingFiles.Count) overlay file(s) missing" -ForegroundColor Yellow
} else {
    Write-Host "      -> All overlay files present" -ForegroundColor Green
}
Write-Host ""

# ---------- 4. Copy skills ----------
Write-Host "[3/5] Copy skills to .qoder\skills\" -ForegroundColor Green
if ($DryRun) {
    foreach ($d in $SkillDirs) {
        $dst = Join-Path $SkillsDst $d.Name
        Write-Host "      [DryRun] $($d.FullName) -> $dst"
    }
} else {
    if (-not (Test-Path $SkillsDst)) {
        New-Item -ItemType Directory -Path $SkillsDst -Force | Out-Null
    }
    foreach ($d in $SkillDirs) {
        $dst = Join-Path $SkillsDst $d.Name
        # robocopy: /E recursive incl. empty /XO skip older /NFL /NDL /NJH /NJS /NP silent
        $robocopyArgs = @($d.FullName, $dst, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
        if (-not $Force) { $robocopyArgs += '/XO' }
        & robocopy @robocopyArgs | Out-Null
        # robocopy: 0-7 = success; >=8 = error
        if ($LASTEXITCODE -ge 8) {
            Write-Error "      [FAIL] $($d.Name) copy failed (robocopy exit=$LASTEXITCODE)"
            exit 1
        }
        Write-Host "      [OK] $($d.Name)"
    }
}
Write-Host ""

# ---------- 5. Init overlay or print reminder ----------
Write-Host "[4/5] Overlay init:" -ForegroundColor Green

$OverlayTplSrc = Join-Path $SkillsSrc 'busi-project-init\references'
$TplMap = @{
    'AGENT.md'         = 'AGENT.md.template'
    'coding-rules.md'  = 'coding-rules.md.template'
    'overlay-spec.md'  = 'overlay-spec.md.template'
}

if ($MissingFiles.Count -eq 0) {
    Write-Host "      [OK] No overlay files missing, skip init."
} elseif ($InitOverlay) {
    # Non-interactive: copy template files for all missing overlays
    if (-not (Test-Path $AgentOverlay)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $AgentOverlay -Force | Out-Null
        }
        Write-Host "      [CREATE] .agent\ directory"
    }
    foreach ($f in $MissingFiles) {
        $tplFile = $TplMap[$f]
        $tplPath = Join-Path $OverlayTplSrc $tplFile
        $dstPath = Join-Path $AgentOverlay $f
        if (-not (Test-Path $tplPath)) {
            Write-Warning "      [WARN] Template not found: $tplPath, skip $f"
            continue
        }
        if ($DryRun) {
            Write-Host "      [DryRun] $tplPath -> $dstPath"
        } else {
            Copy-Item -Path $tplPath -Destination $dstPath -Force
            Write-Host "      [INIT] .agent\$f (from template, TODO markers need filling)" -ForegroundColor Yellow
        }
    }
    Write-Host ""
    Write-Host "      WARNING: Template files contain <!-- TODO --> markers." -ForegroundColor Yellow
    Write-Host "      Open .agent\*.md and search for TODO to fill project-specific values." -ForegroundColor Yellow
    Write-Host "      Or tell AI in Qoder: 'chu shi hua xiang mu' (init project) for guided init." -ForegroundColor Yellow
} else {
    # No -InitOverlay: print prominent reminder
    Write-Host "      $($MissingFiles.Count) overlay file(s) missing:" -ForegroundColor Yellow
    foreach ($f in $MissingFiles) {
        Write-Host "        - .agent\$f" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "      +-----------------------------------------------+" -ForegroundColor Yellow
    Write-Host "      |  OVERLAY NOT READY                            |" -ForegroundColor Yellow
    Write-Host "      |  Skills need .agent/ overlay files to work.  |" -ForegroundColor Yellow
    Write-Host "      |                                               |" -ForegroundColor Yellow
    Write-Host "      |  Option A (recommended):                      |" -ForegroundColor Yellow
    Write-Host "      |    Open project in Qoder, tell AI:           |" -ForegroundColor Yellow
    Write-Host "      |    'chu shi hua xiang mu' (init project)     |" -ForegroundColor Yellow
    Write-Host "      |    -> AI guided overlay generation           |" -ForegroundColor Yellow
    Write-Host "      |                                               |" -ForegroundColor Yellow
    Write-Host "      |  Option B (non-interactive):                 |" -ForegroundColor Yellow
    Write-Host "      |    Re-run with -InitOverlay flag:            |" -ForegroundColor Yellow
    Write-Host "      |    .\install.ps1 -TargetProject <path>       |" -ForegroundColor Yellow
    Write-Host "      |           -InitOverlay                       |" -ForegroundColor Yellow
    Write-Host "      |    -> Copies template files with TODO marks |" -ForegroundColor Yellow
    Write-Host "      +-----------------------------------------------+" -ForegroundColor Yellow
}
Write-Host ""

# ---------- 6. Print trigger keyword cheatsheet ----------
Write-Host "[5/5] Install done. Trigger keywords (ASCII-only display, full keywords in README.md):" -ForegroundColor Green
$triggerMap = @(
    @{ skill = 'busi-project-init';     trigger = 'init project / chu shi hua xiang mu' }
    @{ skill = 'busi-req-analyze';       trigger = 'analyze req / parse requirement doc' }
    @{ skill = 'busi-req-clarify';       trigger = 'clarify req / interrogate' }
    @{ skill = 'busi-api-spec';          trigger = 'api spec / interface spec' }
    @{ skill = 'busi-design-doc';        trigger = 'design doc / design document' }
    @{ skill = 'busi-dev-spec';          trigger = 'write dev spec' }
    @{ skill = 'busi-dev-loop';          trigger = 'api skeleton / start coding' }
    @{ skill = 'busi-coding-rules';      trigger = 'coding rules' }
    @{ skill = 'busi-api-test';          trigger = 'generate tests / api test' }
    @{ skill = 'busi-iter-summary';      trigger = 'iter summary / handover' }
    @{ skill = 'busi-flow-orchestrator'; trigger = 'start full flow / begin v{ver}' }
)
foreach ($t in $triggerMap) {
    "      {0,-30}  {1}" -f $t.skill, $t.trigger | Write-Host
}
Write-Host ""
Write-Host "==== Done ====" -ForegroundColor Cyan
Write-Host "Next: reopen $TargetProject in Qoder; skills will be auto-detected." -ForegroundColor Cyan
if ($MissingFiles.Count -gt 0 -and -not $InitOverlay) {
    Write-Host "      -> Reminder: init overlay before starting B2-B9 flow." -ForegroundColor Yellow
}
Write-Host ""

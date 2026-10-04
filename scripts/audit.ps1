<#
.SYNOPSIS
  Pre-push audit: structure, secrets, the agent surface, and organization neutrality.

.DESCRIPTION
  Four passes. Each is non-fatal on its own; the script exits 1 if any produced a
  finding, so it can gate a push without any single pass being able to block for a
  reason nobody can see.

  A pass that cannot run is counted as a FINDING, never as a pass. A skipped check
  reported as green is the failure mode this whole system is built to avoid, and it
  would be embarrassing for the auditor to commit it.

  This duplicates the CI neutrality gate deliberately: catching it here costs a minute,
  catching it in CI costs a round trip.
#>
[CmdletBinding()]
param([string]$Root = (Resolve-Path "$PSScriptRoot\.."))
$ErrorActionPreference = 'Continue'
$Root = (Resolve-Path $Root).Path
$findings = 0

Write-Host "Audit: $Root`n" -ForegroundColor Cyan
$python = Get-Command python -ErrorAction SilentlyContinue

Write-Host "1. Structure and gates" -ForegroundColor Cyan
if ($python) {
  & python (Join-Path $Root 'scripts/validate-structure.py')
  if ($LASTEXITCODE -ne 0) { $findings++ }
} else {
  Write-Host "  python not on PATH - COUNTED AS A FINDING, not skipped" -ForegroundColor Yellow
  $findings++
}

Write-Host "`n2. Secret scan" -ForegroundColor Cyan
$gitleaks = Get-Command gitleaks -ErrorAction SilentlyContinue
if ($gitleaks) {
  & gitleaks detect --no-git --source $Root --redact
  if ($LASTEXITCODE -ne 0) { $findings++ }
} elseif ($python) {
  Write-Host "  gitleaks not found - using the built-in taxonomy instead"
  $bad = 0
  Get-ChildItem $Root -Recurse -File -Include *.ts,*.js,*.py,*.json,*.yml,*.yaml,*.md,*.ps1 |
    Where-Object { $_.FullName -notmatch 'node_modules|\.git|\\out\\|\\dist\\|__pycache__|\\inbox\\|\\extracted\\' } |
    ForEach-Object {
      & python (Join-Path $Root 'scripts/redact.py') --from-file $_.FullName | Out-Null
      if ($LASTEXITCODE -eq 3) {
        Write-Host "  HIGH finding in $($_.FullName)" -ForegroundColor Red
        $bad++
      }
    }
  if ($bad -gt 0) { $findings++ } else { Write-Host "  no HIGH-tier findings" }
} else {
  Write-Host "  no scanner available - COUNTED AS A FINDING" -ForegroundColor Yellow
  $findings++
}

Write-Host "`n3. Agent surface" -ForegroundColor Cyan
if ($python) {
  & python (Join-Path $Root 'scripts/audit-agent-surface.py')
  if ($LASTEXITCODE -ne 0) { $findings++ }
} else {
  Write-Host "  python not on PATH - COUNTED AS A FINDING" -ForegroundColor Yellow
  $findings++
}

Write-Host "`n4. Organization neutrality" -ForegroundColor Cyan
$pattern = 'charlesschwab|schwab'
$exclude = @('validate-structure.py', 'audit.ps1', 'ci.yml', 'AI-ORCHESTRATOR-MASTER-BLUEPRINT.md', 'hub.config.json')
$hits = Get-ChildItem $Root -Recurse -File -Include *.ts,*.js,*.json,*.yml,*.yaml,*.md,*.py,*.ps1,*.tmpl |
  Where-Object {
    $_.FullName -notmatch 'node_modules|\.git|\\out\\|\\dist\\|\\overlays\\|__pycache__' -and
    $exclude -notcontains $_.Name
  } | Select-String -Pattern $pattern
if ($hits) {
  Write-Host "  $($hits.Count) foreign org reference(s):" -ForegroundColor Red
  $hits | Select-Object -First 10 | ForEach-Object { Write-Host "    $($_.Path):$($_.LineNumber)" }
  $findings++
} else {
  Write-Host "  clean"
}

Write-Host ""
if ($findings -gt 0) {
  Write-Host "AUDIT FAILED: $findings pass(es) produced findings or could not run." -ForegroundColor Red
  exit 1
}
Write-Host "AUDIT CLEAN" -ForegroundColor Green
exit 0

<#
.SYNOPSIS
  Secondary install path: link the hub into ~/.claude/ directly, without the marketplace.

.DESCRIPTION
  The primary distribution is the Claude Code plugin marketplace. This exists for the
  two cases the marketplace does not serve:

    - an air-gapped machine with no access to the plugin source
    - a pinned version, where a team wants exactly this checkout and no updates

  It is deliberately NOT the default. Hand-rolled installation means owning ownership
  detection, orphan pruning, prefix collisions, Windows symlink semantics, and upgrade
  migrations — a body of accidental complexity that the plugin path exists to avoid.
  Keeping this off the critical path is the whole point of having it.

  Symlinks on Windows need Developer Mode or an elevated shell. Where that is not
  available this copies and says so plainly, because a copy the user believes is a link
  will silently stop reflecting their hub edits.
#>
[CmdletBinding()]
param(
  [string]$HubPath = (Resolve-Path "$PSScriptRoot\.."),
  [string]$ClaudeHome = (Join-Path $HOME '.claude'),
  [switch]$Copy,
  [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
$HubPath = (Resolve-Path $HubPath).Path

$targets = @(
  @{ src = 'skills';   dst = 'skills' },
  @{ src = 'agents';   dst = 'agents' },
  @{ src = 'commands'; dst = 'commands' }
)
$markerName = '.orchestrator-owned'

if ($Uninstall) {
  Write-Host "Removing orchestrator links from $ClaudeHome" -ForegroundColor Cyan
  foreach ($t in $targets) {
    $dst = Join-Path $ClaudeHome $t.dst
    if (-not (Test-Path $dst)) { continue }
    $marker = Join-Path $dst $markerName
    $item = Get-Item $dst -Force
    if ($item.LinkType -eq 'SymbolicLink') {
      Remove-Item $dst -Force
      Write-Host "  unlinked $dst"
    } elseif (Test-Path $marker) {
      Remove-Item $dst -Recurse -Force
      Write-Host "  removed $dst (ownership marker present)"
    } else {
      Write-Host "  SKIPPED $dst - no ownership marker, so it is not ours to remove" -ForegroundColor Yellow
    }
  }
  exit 0
}

Write-Host "Installing the orchestrator into $ClaudeHome" -ForegroundColor Cyan
Write-Host "  This is the SECONDARY path. Prefer:" -ForegroundColor Yellow
Write-Host "    /plugin marketplace add abhishek-narula-algoworks/Ai-Orchestration-Hub" -ForegroundColor Yellow
Write-Host "    /plugin install orchestrator@algoworks" -ForegroundColor Yellow
Write-Host ""

New-Item -ItemType Directory -Force -Path $ClaudeHome | Out-Null

foreach ($t in $targets) {
  $src = Join-Path $HubPath $t.src
  $dst = Join-Path $ClaudeHome $t.dst
  if (-not (Test-Path $src)) { continue }

  if (Test-Path $dst) {
    $marker = Join-Path $dst $markerName
    $item = Get-Item $dst -Force
    if ($item.LinkType -ne 'SymbolicLink' -and -not (Test-Path $marker)) {
      Write-Host "  SKIPPED $dst - it exists and carries no ownership marker." -ForegroundColor Yellow
      Write-Host "          Overwriting an existing skills directory is not a decision this"
      Write-Host "          script gets to make. Move it aside and re-run."
      continue
    }
    Remove-Item $dst -Recurse -Force
  }

  $linked = $false
  if (-not $Copy) {
    try {
      New-Item -ItemType SymbolicLink -Path $dst -Target $src -ErrorAction Stop | Out-Null
      Write-Host "  linked  $($t.dst) -> $src"
      $linked = $true
    } catch {
      Write-Host "  symlink refused (needs Developer Mode or an elevated shell) - copying instead" -ForegroundColor Yellow
    }
  }
  if (-not $linked) {
    Copy-Item $src $dst -Recurse -Force
    @{ hub = $HubPath; installedAt = (Get-Date).ToString('o'); mode = 'copy' } |
      ConvertTo-Json | Set-Content (Join-Path $dst $markerName) -Encoding utf8
    Write-Host "  copied  $($t.dst)  (a COPY - hub edits will NOT appear until you re-run this)"
  }
}

Write-Host "`nInstalled." -ForegroundColor Green
Write-Host "  Uninstall with: pwsh scripts/install-team.ps1 -Uninstall"

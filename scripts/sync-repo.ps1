<#
.SYNOPSIS
  Refresh an already-connected repository from the hub.

.DESCRIPTION
  Sync is for repositories that are already connected. With no install state this
  refuses and points at connect-repo.ps1 — creating one here would produce an install
  record that does not describe what actually happened.

  Under the plugin model there is very little to sync: the plugin carries the content.
  This refreshes the repo context file, re-applies the managed .gitignore block, and
  updates the install state. A repository connected with -Vendor also gets its vendored
  copies refreshed, ownership-gated.
#>
[CmdletBinding()]
param(
  [string]$Repo = (Get-Location).Path,
  [string]$HubPath = (Resolve-Path "$PSScriptRoot\.."),
  [switch]$Force
)
$ErrorActionPreference = 'Stop'

$Repo = (Resolve-Path $Repo).Path
$statePath = Join-Path $Repo '.github/orchestrator-install.json'

if (-not (Test-Path $statePath)) {
  Write-Error "No .github/orchestrator-install.json in $Repo. Sync is for already-connected repositories; run scripts/connect-repo.ps1 first."
  exit 1
}

$state = Get-Content $statePath -Raw | ConvertFrom-Json
$hub = Get-Content (Join-Path $HubPath 'hub.config.json') -Raw | ConvertFrom-Json

Write-Host "Syncing $Repo" -ForegroundColor Cyan
Write-Host "  installed hub $($state.hubVersion) -> current $($hub.hub.version)"

if ($state.hubVersion -ne $hub.hub.version) {
  Write-Host "  version changed — run the migrations after this sync:" -ForegroundColor Yellow
  Write-Host "    python scripts/orchestrator.py upgrade --repo $Repo"
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  Write-Error "python is not on PATH. Install Python 3.11+; the sync path is Python so it works on Linux and in CI too."
  exit 1
}

$genArgs = @((Join-Path $HubPath 'scripts/context-gen.py'), '--repo', $Repo)
if ($Force) { $genArgs += '--force' }
& python @genArgs

& python (Join-Path $HubPath 'scripts/gitignore.py') --repo $Repo apply

$state.hubVersion = $hub.hub.version
$state.lastValidatedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$state | ConvertTo-Json -Depth 8 | Set-Content $statePath -Encoding utf8

Write-Host "`nSynced." -ForegroundColor Green
Write-Host "  Run 'git diff .github/' to review exactly what changed."
Write-Host "  Preserved as always: the Integration Points and Verified Commands sections."

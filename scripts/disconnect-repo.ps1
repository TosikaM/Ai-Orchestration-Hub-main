<#
.SYNOPSIS
  Disconnect a repository, removing only what the install state records.

.DESCRIPTION
  -DryRun is the documented first step and appears in every example, because the
  interesting question is not "will this work" but "what exactly are you about to touch".

  This removes only paths recorded as written by us, reverses the managed .gitignore
  block, and clears any skip-worktree bits we set. A foreign file at a path we would
  have used is named and left alone: never clean up a file you cannot prove you created.

  The logic itself lives in scripts/orchestrator.py so the same behaviour is available
  on Linux and in CI. This is a convenience wrapper, not a second implementation.
#>
[CmdletBinding()]
param(
  [string]$Repo = (Get-Location).Path,
  [string]$HubPath = (Resolve-Path "$PSScriptRoot\.."),
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path $Repo).Path

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  Write-Error "python is not on PATH. The uninstall logic lives in scripts/orchestrator.py."
  exit 1
}

$callArgs = @((Join-Path $HubPath 'scripts/orchestrator.py'), '--repo', $Repo, 'uninstall')
if ($DryRun) { $callArgs += '--dry-run' }
& python @callArgs
exit $LASTEXITCODE

<#
.SYNOPSIS
  Connect a repository to the AI Orchestrator.

.DESCRIPTION
  Under the plugin distribution model this writes very little into the consumer repo —
  the plugin already carries the agents, skills, prompts, contexts, and hooks. What
  lands here is the repo's own profile and the install state that makes `doctor` and
  `uninstall` possible.

  That is the biggest simplification in this architecture and it is worth stating: the
  managed .gitignore block drops from ten paths to two, and the whole class of bug where
  a sync overwrites a consumer's own file largely disappears, because we stop writing
  files into repositories that did not ask for them.

  The vendoring path (-Vendor) still exists for a repo that wants the content on disk
  for offline or audit reasons. It keeps the ownership gate, because a vendoring path
  that overwrites without asking is still wrong behaviour even when it is rare.

.EXAMPLE
  pwsh scripts/connect-repo.ps1 -Repo C:\src\command-api -Profile standard
  pwsh scripts/connect-repo.ps1 -Repo C:\src\web -Profile reviewer -Vendor
#>
[CmdletBinding()]
param(
  [string]$Repo = (Get-Location).Path,
  [string]$HubPath = (Resolve-Path "$PSScriptRoot\.."),
  [ValidateSet('context-only', 'standard', 'reviewer', 'band-member')]
  [string]$InstallProfile = 'standard',
  [string[]]$With = @(),
  [string[]]$Without = @(),
  [switch]$Vendor,
  [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'

function Write-Step($message) { Write-Host "  $message" }
function Write-Warn($message) { Write-Host "  ! $message" -ForegroundColor Yellow }

$Repo = (Resolve-Path $Repo).Path
$HubPath = (Resolve-Path $HubPath).Path

Write-Host "Connecting $Repo" -ForegroundColor Cyan
Write-Host "  hub:     $HubPath"
Write-Host "  profile: $InstallProfile"
Write-Host ""

# Connecting a non-repository silently is how orphaned .github folders happen.
if (-not (Test-Path (Join-Path $Repo '.git'))) {
  Write-Error "No .git in $Repo. Connecting a non-repository is refused: the install state would have nothing to belong to."
  exit 1
}
if (-not (Test-Path (Join-Path $HubPath 'hub.config.json'))) {
  Write-Error "$HubPath does not look like the orchestrator hub (no hub.config.json)."
  exit 1
}

$hub = Get-Content (Join-Path $HubPath 'hub.config.json') -Raw | ConvertFrom-Json
$profiles = Get-Content (Join-Path $HubPath 'config/install-profiles.json') -Raw | ConvertFrom-Json
$resolved = @($profiles.profiles.$InstallProfile.components)
if ($With)    { $resolved += $With }
if ($Without) { $resolved = $resolved | Where-Object { $Without -notcontains $_ } }

Write-Step "components: $($resolved -join ', ')"

$githubDir = Join-Path $Repo '.github'
$operations = @()

if (-not $WhatIf) { New-Item -ItemType Directory -Force -Path $githubDir | Out-Null }

# ---------------------------------------------------------------- repo context
Write-Host "`nGenerating the repo context file..." -ForegroundColor Cyan
if (-not $WhatIf) {
  $python = (Get-Command python -ErrorAction SilentlyContinue)
  if (-not $python) {
    Write-Warn "python is not on PATH. Skipping context generation."
    Write-Warn "Install Python 3.11+ and run: python scripts/context-gen.py --repo `"$Repo`""
  } else {
    & python (Join-Path $HubPath 'scripts/context-gen.py') --repo $Repo
    $contextFile = Join-Path $githubDir 'orchestrator-context.md'
    if (Test-Path $contextFile) {
      $hash = (Get-FileHash $contextFile -Algorithm SHA256).Hash.ToLower()
      $operations += @{ op = 'write'; path = '.github/orchestrator-context.md'; sha256 = $hash; ownership = 'strong' }
    }
  }
}

# ---------------------------------------------------------------- optional vendoring
if ($Vendor) {
  Write-Host "`nVendoring content into .github/ (ownership-gated)..." -ForegroundColor Cyan
  Write-Warn "Vendoring duplicates what the plugin already carries. Do this only for an"
  Write-Warn "offline or audit requirement — otherwise an upgrade becomes N pull requests."

  $backupRoot = Join-Path $HOME ".orchestrator\backups\$(Get-Date -Format 'yyyyMMdd-HHmmss')"
  foreach ($dir in @('agents', 'skills', 'prompts', 'contexts', 'instructions')) {
    $src = Join-Path $HubPath $dir
    if (-not (Test-Path $src)) { continue }
    $dst = Join-Path $githubDir $dir
    foreach ($file in Get-ChildItem $src -Recurse -File) {
      $rel = $file.FullName.Substring($src.Length).TrimStart('\', '/')
      $target = Join-Path $dst $rel
      $relPath = ".github/$dir/$($rel -replace '\\','/')"

      if (Test-Path $target) {
        # We never wrote this before -> it is a foreign file. Report and skip.
        $prior = $operations | Where-Object { $_.path -eq $relPath }
        if (-not $prior) {
          Write-Warn "SKIPPED foreign file: $relPath"
          $operations += @{ op = 'skip-foreign'; path = $relPath; reason = 'not written by us' }
          continue
        }
        $current = (Get-FileHash $target -Algorithm SHA256).Hash.ToLower()
        if ($current -ne $prior.sha256) {
          $backup = Join-Path $backupRoot $relPath
          if (-not $WhatIf) {
            New-Item -ItemType Directory -Force -Path (Split-Path $backup) | Out-Null
            Copy-Item $target $backup -Force
          }
          Write-Warn "backed up your edit: $relPath -> $backup"
        }
      }
      if (-not $WhatIf) {
        New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
        Copy-Item $file.FullName $target -Force
        $hash = (Get-FileHash $target -Algorithm SHA256).Hash.ToLower()
        $operations += @{ op = 'write'; path = $relPath; sha256 = $hash; ownership = 'strong' }
      }
    }
    Write-Step "vendored $dir/"
  }

  # Render the consumer connector from templates/generic/consumer-instruction.template.md.
  #
  # This runs only on the vendoring path, deliberately. Under the plugin model the
  # connector instructions are carried by the plugin and discovered natively, so a repo
  # that has not opted into vendoring needs no local copy. A repo that HAS opted in wants
  # one with its own values filled in rather than a file full of {{PLACEHOLDER}}.
  #
  # A template nothing renders is the same defect as a hook nothing executes: it looks
  # like a shipped capability and is a dead file.
  $tpl = Join-Path $HubPath 'templates/generic/consumer-instruction.template.md'
  if (Test-Path $tpl) {
    $stack = 'not detected'
    $arch  = 'not detected'
    $contextFile = Join-Path $githubDir 'orchestrator-context.md'
    if (Test-Path $contextFile) {
      $ctx = Get-Content $contextFile -Raw
      # The literal '| **Tech Stack**: |' row shape is a contract — the connect path
      # matches on it to recover a repo's stack. Restyling that table row silently makes
      # every connected repo record "unknown".
      if ($ctx -match '\|\s*\*\*Tech Stack\*\*:\s*\|\s*([^|]+?)\s*\|') { $stack = $Matches[1].Trim() }
      if ($ctx -match '\|\s*Architecture\s*\|\s*([^|]+?)\s*\|')        { $arch  = $Matches[1].Trim() }
    }

    $subs = ($resolved | ForEach-Object { "- $_" }) -join "`n"
    $today = Get-Date -Format 'yyyy-MM-dd'
    $seeContext = 'see .github/orchestrator-context.md'

    # A plain ordered map and one loop. Deliberately not a chained .Replace() across
    # several lines: Windows PowerShell 5.1 does not continue a method chain over a
    # trailing dot, and the parse error it produces points at the closing brace of the
    # enclosing block rather than at the chain, which is a genuinely confusing half hour.
    $substitutions = [ordered]@{
      '{{REPO_NAME}}'         = (Split-Path $Repo -Leaf)
      '{{ORG}}'               = $hub.org.displayName
      '{{CONNECTION_DATE}}'   = $today
      '{{LAST_REFRESH}}'      = $today
      '{{TECH_STACK}}'        = $stack
      '{{ARCHITECTURE}}'      = $arch
      '{{FRAMEWORK_VERSION}}' = $seeContext
      '{{TEST_FRAMEWORK}}'    = $seeContext
    }

    $rendered = Get-Content $tpl -Raw
    foreach ($key in $substitutions.Keys) {
      # String.Replace, not -replace: the values are literal text and a regex operator
      # would treat a '$' or a backslash in a repo name as a backreference or an escape.
      $rendered = $rendered.Replace($key, [string]$substitutions[$key])
    }

    # Collapse the subscriptions loop to the resolved component list. Split/join rather
    # than [regex]::Replace with a MatchEvaluator, for the same 5.1 parsing reason.
    $loopStart = '{{#SUBSCRIPTIONS}}'
    $loopEnd   = '{{/SUBSCRIPTIONS}}'
    $before = $rendered.IndexOf($loopStart)
    $after  = $rendered.IndexOf($loopEnd)
    if ($before -ge 0 -and $after -gt $before) {
      $rendered = $rendered.Substring(0, $before) + $subs +
                  $rendered.Substring($after + $loopEnd.Length)
    }

    $connectorDir = Join-Path $githubDir 'instructions'
    $connectorPath = Join-Path $connectorDir 'orchestrator-connector.instructions.md'
    if (-not $WhatIf) {
      New-Item -ItemType Directory -Force -Path $connectorDir | Out-Null
      Set-Content $connectorPath $rendered -Encoding utf8
      $hash = (Get-FileHash $connectorPath -Algorithm SHA256).Hash.ToLower()
      $operations += @{ op = 'write'; path = '.github/instructions/orchestrator-connector.instructions.md'; sha256 = $hash; ownership = 'strong' }
    }
    Write-Step "rendered the consumer connector"

    $left = ([regex]::Matches($rendered, '\{\{[A-Za-z0-9_#/]+\}\}')).Count
    if ($left -gt 0) {
      Write-Warn "$left placeholder(s) left unfilled in the connector — inspect $connectorPath"
    }
  }
}

# ---------------------------------------------------------------- gitignore
Write-Host "`nApplying the managed .gitignore block..." -ForegroundColor Cyan
if (-not $WhatIf) {
  $python = (Get-Command python -ErrorAction SilentlyContinue)
  if ($python) {
    & python (Join-Path $HubPath 'scripts/gitignore.py') --repo $Repo apply
    $operations += @{ op = 'gitignore-block'; path = '.gitignore'; markerBegin = '# >>> AI Orchestrator (auto-managed — do not edit) >>>' }
  } else {
    Write-Warn "python not on PATH — skipped."
  }
}

# ---------------------------------------------------------------- install state
$installState = [ordered]@{
  schemaVersion   = 'orchestrator.install.v1'
  installedAt     = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  lastValidatedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  hubRepository   = $hub.hub.repository
  hubBranch       = $hub.hub.branch
  hubVersion      = $hub.hub.version
  overlayProfile  = $hub.overlay.profile
  request         = @{ profile = $InstallProfile; with = $With; without = $Without; vendored = [bool]$Vendor }
  resolution      = @{ components = $resolved }
  operations      = $operations
}

$statePath = Join-Path $githubDir 'orchestrator-install.json'
if ($WhatIf) {
  Write-Host "`n--WhatIf: would write $statePath" -ForegroundColor Yellow
} else {
  $json = $installState | ConvertTo-Json -Depth 8
  [IO.File]::WriteAllText($statePath, $json, (New-Object Text.UTF8Encoding $false))
  Write-Host "`nWrote $statePath" -ForegroundColor Green
}

Write-Host "`nConnected." -ForegroundColor Green
Write-Host "  Next:"
Write-Host "    /orchestrator-init                           # in Claude Code, refine the context"
Write-Host "    python scripts/orchestrator.py doctor        # confirm the install"
Write-Host ""
Write-Host "  The plugin carries the skills and agents. Only the context file and the install"
Write-Host "  state live in this repository, which is why an upgrade is one command rather than"
Write-Host "  a pull request per repo."

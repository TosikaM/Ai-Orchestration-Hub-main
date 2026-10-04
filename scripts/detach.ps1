<#
.SYNOPSIS
  Run a long command detached, with a lock, a watchdog, and a guaranteed exit sentinel.

.DESCRIPTION
  A plain background task lives in the harness's process group. A signal on a turn
  boundary, a stopped monitor, or an interruption kills it mid-flight — the observed
  failure is a run terminated roughly forty minutes in, with no record of why.

  This wrapper gives a long run four things:

    a fresh process, so it survives a signal to the harness's group
    a machine-wide lock, so concurrent worktrees serialize instead of saturating an API
    a watchdog timeout, so a hung run ends rather than living forever
    a run-scoped log ending in a GUARANTEED sentinel:  ### EXIT=<code> ###

  The sentinel is the important one. Every run writes it, on success and on failure
  alike, which means a poller can break on the sentinel rather than on a timer.
  **Silence is never mistaken for success** — a poller that gives up on a timeout cannot
  tell a finished run from a killed one, and will report the killed one as complete.

.EXAMPLE
  pwsh scripts/detach.ps1 -Label fix-flaky-tests -Timeout 1800 -Lock -Command "npm test"
  Get-Content $HOME\.orchestrator\runs\fix-flaky-tests-*.log -Wait
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Command,
  [string]$Label = 'run',
  [int]$Timeout = 1800,
  [switch]$Lock,
  [string]$WorkingDirectory = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'

$stateHome = Join-Path $HOME '.orchestrator'
$runsDir   = Join-Path $stateHome 'runs'
$locksDir  = Join-Path $stateHome 'locks'
New-Item -ItemType Directory -Force -Path $runsDir, $locksDir | Out-Null

$stamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
$safe    = ($Label -replace '[^A-Za-z0-9._-]', '-')
$logPath = Join-Path $runsDir "$safe-$stamp.log"
$lockPath = Join-Path $locksDir "detach-$safe.lock"

if ($Lock) {
  if (Test-Path $lockPath) {
    $existing = Get-Content $lockPath -Raw | ConvertFrom-Json
    $age = (Get-Date) - [datetime]$existing.acquiredAt
    if ($age.TotalSeconds -lt $Timeout) {
      Write-Host "Locked by PID $($existing.pid) since $($existing.acquiredAt)." -ForegroundColor Yellow
      Write-Host "Waiting rather than running concurrently: two runs against the same model API"
      Write-Host "saturate it and both get slower than one would have been."
      exit 1
    }
    Write-Host "Stale lock (older than the timeout). Reclaiming." -ForegroundColor Yellow
  }
  @{ pid = $PID; label = $safe; acquiredAt = (Get-Date).ToString('o') } |
    ConvertTo-Json | Set-Content $lockPath -Encoding utf8
}

# The child writes the sentinel itself, in a finally block, so it is written even when
# the command throws. A sentinel the parent writes would be missing exactly when the
# parent is what died.
$childScript = @'
param($Command, $LogPath, $WorkingDirectory, $Timeout)
$ErrorActionPreference = 'Continue'
Set-Location $WorkingDirectory
$exitCode = 1
try {
  "### START $(Get-Date -Format o) ###" | Out-File $LogPath -Encoding utf8
  "### CMD $Command" | Out-File $LogPath -Append -Encoding utf8
  $job = Start-Job -ScriptBlock { param($c, $d) Set-Location $d; Invoke-Expression $c 2>&1 } -ArgumentList $Command, $WorkingDirectory
  if (Wait-Job $job -Timeout $Timeout) {
    Receive-Job $job | Out-File $LogPath -Append -Encoding utf8
    $exitCode = 0
  } else {
    Stop-Job $job
    "### WATCHDOG: exceeded ${Timeout}s, job stopped ###" | Out-File $LogPath -Append -Encoding utf8
    $exitCode = 124
  }
  Remove-Job $job -Force -ErrorAction SilentlyContinue
} catch {
  $_ | Out-String | Out-File $LogPath -Append -Encoding utf8
  $exitCode = 1
} finally {
  "### EXIT=$exitCode ###" | Out-File $LogPath -Append -Encoding utf8
}
'@

$childPath = Join-Path $runsDir "$safe-$stamp.child.ps1"
$childScript | Set-Content $childPath -Encoding utf8

$process = Start-Process -FilePath 'powershell.exe' `
  -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $childPath,
                  '-Command', $Command, '-LogPath', $logPath,
                  '-WorkingDirectory', $WorkingDirectory, '-Timeout', $Timeout) `
  -WindowStyle Hidden -PassThru

Write-Host "Detached run started." -ForegroundColor Green
Write-Host "  label:   $safe"
Write-Host "  pid:     $($process.Id)"
Write-Host "  log:     $logPath"
Write-Host "  timeout: ${Timeout}s"
if ($Lock) { Write-Host "  lock:    $lockPath" }
Write-Host ""
Write-Host "Follow it with:"
Write-Host "  Get-Content `"$logPath`" -Wait"
Write-Host ""
Write-Host "Poll by BREAKING ON THE SENTINEL, never on a timer:"
Write-Host '  while (-not (Select-String -Path $log -Pattern "### EXIT=" -Quiet)) { Start-Sleep 10 }'
Write-Host ""
Write-Host "Every run writes '### EXIT=<code> ###' as its last line, on success and on failure."
Write-Host "A poller that gives up on a timeout cannot tell a finished run from a killed one."

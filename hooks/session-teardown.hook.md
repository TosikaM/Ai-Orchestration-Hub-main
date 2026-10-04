---
name: session-teardown
trigger: SessionEnd
matcher: ".*"
profiles: [minimal, standard, strict]
mode: sync
blocking: false
handler: hooks/runtime/handlers/session-teardown.js
description: Releases cross-repo band locks held by the ending session, prunes stale session scratch files, and records a session-end telemetry line when telemetry is enabled.
---

# Session Teardown

This fires at `SessionEnd` and does two pieces of cleanup plus one optional record. It is
short, it never blocks, and both of its jobs exist because the alternative is a stuck
system that nobody can diagnose.

## Why this exists

**Locks.** A cross-repo band serializes work across repositories so two agents do not
implement the same shared contract twice. Serialization means a lock, and a lock that
outlives the session that took it blocks every future run. The symptom is not an error —
it is a hang, or a band that refuses to start, with nothing in any log saying why. Stale
lock files are one of the most expensive small bugs a system like this can have, because
the cost is paid in confusion rather than in a stack trace.

**Session files.** Session scratch state accumulates one file per conversation, forever,
and `doctor` cannot tell "in flight" from "abandoned" if nothing ever marks the
difference. Neither problem is urgent on any given day and both are corrosive over
months.

## What it does

`releaseLocks(sessionId)` reads every file in the state `locks/` directory and deletes
the ones this session owns — plus any whose `acquiredAt` is more than an hour old,
whoever holds them. That second condition is the important one and it is the reason locks
carry a session id and a timestamp: a crashed session never reaches `SessionEnd`, so the
age-based reclaim is what actually guarantees release. This hook is the fast path; the
timestamp is the guarantee.

`pruneSessionFiles()` removes files in the state `sessions/` directory older than seven
days. Session scratch is a working set, not a history, and an old one is noise that makes
the current one harder to find.

If `ORCHESTRATOR_TELEMETRY` is `on`, it appends a hash-chained `session-end` record
carrying the repository slug and the session id — nothing else. See
`telemetry.hook.md` for what that file is and is not.

Every step is wrapped so a failure is skipped rather than thrown. A teardown that throws
at session end has nowhere useful to report and nothing to gain.

## Action on a hit

Nothing visible. The handler always returns allow, and the counts it computes are
returned to callers but not surfaced to the user. Teardown is bookkeeping; announcing it
would be noise at exactly the moment nobody is reading.

## Recovery / escape

There is nothing to escape. If the hook does not run — because the session was killed, or
because it is disabled — the recovery is the age-based lock reclaim, which happens on its
own an hour later, and `python scripts/doctor.py` for anything else that looks stuck.

To disable: `ORCHESTRATOR_DISABLED_HOOKS=session:end:teardown`, or
`ORCHESTRATOR_HOOKS_ENABLED=false`. The consequence is a lock that lingers for up to an
hour instead of being released immediately, and session files that accumulate.

## Honest limits

`SessionEnd` is not guaranteed to fire. A killed process, a crashed host, or a machine
that loses power skips it entirely, which is precisely why the age reclaim exists and why
one hour is short. Treat this hook as an optimization on top of a mechanism that has to
work without it.

The age reclaim is blunt in the other direction. A legitimately long band that holds a
lock for more than an hour has it taken by the next session's teardown, and nothing
notices the collision — the sixty-minute constant is a judgment call, not a measurement
of how long a band takes.

Pruning covers the state `sessions/` directory only. The workspace's own
`memory/sessions/` — checkpoints, gate artifacts, band files, learning candidates — is
never touched here, which is deliberate (those are records, not scratch) and does mean
they grow without bound until something else cleans them up.

Locks are keyed to the session id from the payload, which falls back to `'default'` when
none is supplied. Two payload-less sessions look like the same session to this code.

And it is per machine. A lock held by a session on another developer's machine is neither
seen nor released by anything here.

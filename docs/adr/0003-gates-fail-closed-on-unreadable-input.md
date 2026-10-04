# ADR-0003: Blocking gates fail closed on an unreadable payload

- **Status:** Accepted
- **Date:** 2026-09-08
- **Deciders:** Algoworks AI Platform Team
- **Decision log id:** d-0003

## Context

`hooks/runtime/lib/stdin.js` read the hook payload with no size cap and resolved on a
two-second timer. The path that follows from that is short and bad:

```
a large or slow payload
  → the timer fires before the pipe drains
  → `data` holds partial JSON
  → JSON.parse throws; the module returned an empty payload
  → normalize() produced ctx.filePath = '' and ctx.command = ''
  → every gate checked `if (!ctx.filePath) return allow()`
  → ALL FIVE BLOCKING GATES PERMITTED THE ACTION
```

Nothing was logged. Nothing was denied. The reassurance of having gates survived
intact while the protection did not.

The payload sizes that trigger it are ordinary, not adversarial: a `MultiEdit` across a
large file, or a `Bash` call carrying a long heredoc. `hooks/runtime/lib/stdin.js:37`
(previous revision) set `TIMEOUT_MS = 2000` with no cap on accumulated bytes.

Two properties of the system made this maximally expensive. First, every blocking gate
— `fact-force`, `autonomy-gate`, `config-protection`, `destructive-gate`, `human-gate` —
shares this one input path, so a single failure disables all of them simultaneously.
Second, the guards each treat an empty field as "nothing to check", which is correct when
there is genuinely nothing and catastrophic when there is something we failed to read.

## Decision

**A blocking gate that cannot read its input denies the action and says why.**

Truncation is now a propagated fact rather than an invisible one: reads are capped at
1 MiB, a timeout or overflow is reported as `truncated` with a reason, and `run.js` and
`dispatch.js` refuse on behalf of any hook whose registry entry says `blocking: true`.

## Options considered

### Option A — Propagate truncation; blocking gates fail closed (chosen)

- **How it works:** cap the read, distinguish "no input" from "incomplete input", carry
  the flag into `normalize()`, and let the runners refuse for blocking hooks.
- **Cost:** a genuinely oversized payload now blocks work until the operation is split or
  the cap is raised deliberately.
- **What it forecloses:** nothing. The cap is a constant with a comment.

### Option B — Raise the timeout and the buffer, keep failing open (rejected)

- **How it works:** make the window large enough that the failure is rare.
- **Cost:** none visible, which is the problem.
- **Why rejected:** it converts a reproducible failure into an intermittent one. The
  gate would still be off in the failing case, and now the case is rare enough that
  nobody would ever catch it in review. Rare and silent is strictly worse than frequent
  and silent, because rarity is mistaken for correctness.

### Option C — Fail closed for every hook, not only blocking ones (rejected)

- **How it works:** any hook that cannot read its payload refuses.
- **Cost:** `citation-guard`, `learning-capture`, `telemetry` and `context-staleness`
  are advisory. Blocking a turn because a learning could not be recorded trades a real
  work stoppage for a bookkeeping loss.
- **Why rejected:** it inverts the trade the runtime already makes deliberately
  everywhere else — advisory hooks fail open so a bug in a nicety cannot stop work.

## Strongest argument against this decision

It introduces a new way for work to stop, in the code path every single tool call passes
through. If the 1 MiB cap or the 5 s timeout is miscalibrated, the result is not a
degraded gate — it is a developer who cannot edit a file and whose denial message talks
about pipe buffers.

That is a real risk and the honest mitigation is modest: the cap is generous relative to
observed payloads, the timeout was raised from 2 s to 5 s at the same time, and the
denial names the file and constant to change. It is accepted because the alternative is a
security control whose failure mode is silence, and a noisy failure in a gate is
recoverable in a way that a silent one is not.

## Consequences

- **Positive:** the five blocking gates can no longer be disabled by a slow pipe. The
  failure is now loud, attributable and self-describing.
- **Positive:** `truncated` is available to every handler, so a future gate can reason
  about partial input rather than inferring from empty strings.
- **Negative:** a new stop condition on the hottest path in the runtime.
- **Reversal cost:** low — one constant and one branch in each runner, roughly thirty
  minutes. The propagated flag would stay and remain harmless.

## Follow-ups

- A regression test that pipes an oversized payload and asserts a `deny`, once a hook
  test harness exists. This defect is currently prevented by code and documented by this
  ADR, and not yet covered by a test — the honest state, stated rather than implied.
- Audit the other shared input paths for the same shape: a parse failure that resolves to
  an empty value which downstream code reads as "nothing to do".

---
name: session-bootstrap
trigger: SessionStart
matcher: ".*"
profiles: [minimal, standard, strict]
mode: sync
blocking: false
handler: hooks/runtime/handlers/session-bootstrap.js
description: Injects the small always-on set at session start — context freshness, a pending human gate, an in-flight band, settled decisions, and the discovery footprint.
---

# Session Bootstrap

This runs once when a session starts, assembles up to five short sections about the
current repository, and attaches them as `additionalContext`. If none of the five have
anything to say, it returns an empty response and costs nothing but the Node startup.

## Why this exists

The previous architecture had a chat participant that *always* streamed repository
context, memory, and the evidence manifest before any command ran. Injection was
guaranteed. Moving to native skill dispatch loses that guarantee outright: a skill loads
when the model decides to load it, and a model that does not know a fact exists cannot
decide it needs it.

The answer is not to rebuild guaranteed injection — that was expensive and most of what
it pushed went unread. It is to split the difference honestly. A very small set of facts
is pushed unconditionally here, chosen by one test: *could the agent have known to ask
for this?* An open human gate fails that test. A settled decision the agent is about to
reverse fails it. Everything else becomes retrieved on demand, which is the better
pattern anyway and is what progressive disclosure argued for all along.

## What it injects

**Repo context status.** If `.github/orchestrator-context.md` does not exist, it says so
and directs the agent to `/orchestrator-init` before any analysis, because every claim about the
repository is otherwise ungrounded. If it exists but is older than fourteen days, the
section reports the age and tells the agent to treat the layer map as inferred rather
than verified — a downgrade, not a refusal.

**Pending human gate.** Any `*.gate-<phase>.md` in `memory/sessions/` with no matching
`.json` verdict means the pipeline is stopped and waiting. The section names the files
and the two ways to answer them, and says not to advance past them.

**Cross-repo band in flight.** The newest `*.band.json` with repositories still
remaining reports how many are done and which is next, and instructs the agent to consume
the upstream shared contracts as named rather than re-deriving them.

**Settled decisions.** The repository's decision log is replayed — `supersede` and
`redact` events remove the entries they name, `decide` events survive — and the most
recent surviving decisions are listed, capped by
`token-budgets.json → memoryRead.maxInjectedDecisions` (default 8). They are framed as
settled with a standing instruction: if you are about to reverse one, say so explicitly
and say why.

**Discovery footprint**, but only when it is at or over `warnAtPercent` of its ceiling.
This is the text parsed in every session in every repository, so it is the one budget
worth nagging about.

## Action on a hit

`SessionStart` `additionalContext` — an inform. Nothing blocks and nothing is denied.
The body ends with a line naming what was *not* pushed and how to get it: `/analyze` for
structure, `/memory` for learnings, `/repo` for the band, `/knowledge` for the curated
base.

The cap is the point. Session-start injection is the most easily bloated always-on
surface in a system like this — it is where "we load context automatically" quietly
becomes "we spend two thousand tokens before you type" with nobody having decided to. The
body is hard-capped at `token-budgets.json → sessionStart.maxChars` (default 8000), and
when the cap bites the trim is announced in the text rather than happening silently.

## Recovery / escape

There is nothing to recover from; this hook never denies. If the injection is unwanted,
`ORCHESTRATOR_DISABLED_HOOKS=session:start:bootstrap` removes it for the session and
`ORCHESTRATOR_HOOKS_ENABLED=false` removes the runtime.

To make it smaller rather than absent, lower `sessionStart.maxChars` or
`memoryRead.maxInjectedDecisions` in `config/token-budgets.json` — a governance edit,
so config protection will ask you to say why.

## Honest limits

It fires once, at the start. Nothing re-injects when the facts change: a gate opened in
turn thirty is not announced by this hook, and the decision log read at minute zero is
the one the session keeps.

The staleness threshold is a constant in the handler, not a configured value, and
fourteen days is a guess. It is a proxy for "the architecture may have moved", which is
not what file age measures.

The cap truncates by character count. A trim can cut a section mid-sentence; the marker
tells you it happened, but the lost content is lost for that session.

Each section is best-effort and silent on failure. An unreadable or malformed decision
log yields no decisions section and no error — the agent is not told that decisions
exist but could not be read.

The band and gate sections read only this workspace's `memory/sessions/`. Work in flight
in another checkout of the same repository is invisible.

And an injected instruction is still an instruction. "Do not advance past the gate" is
enforced by the human-gate hook, not by this text. The rest of these lines are advice
that the model may or may not act on.

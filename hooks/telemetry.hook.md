---
name: telemetry
trigger: Stop
matcher: ".*"
profiles: [minimal, standard, strict]
mode: async
blocking: false
handler: hooks/runtime/handlers/telemetry.js
description: Appends one local JSONL line per turn recording counts and durations, off unless ORCHESTRATOR_TELEMETRY is explicitly enabled.
---

# Telemetry

At `Stop`, asynchronously, this appends a single record to a local JSONL file describing
the turn that just ended. It is off unless `ORCHESTRATOR_TELEMETRY` is set to `on`, `1`,
`true`, or `yes`, and it runs in `stop:dispatcher:async` so it is never on the user's
critical path.

## Local-only, default-off, no network import

There is no HTTP client in this handler and there is not going to be one. Telemetry
writes to `~/.orchestrator/telemetry.jsonl` through `state.appendChained` and stops.
Nothing is sent anywhere, and the absence of a network dependency in the file is what
makes that claim checkable rather than a promise — you can verify it by reading the
imports.

Default-off is the other half. A tool that starts measuring its users the moment it is
installed has made a decision on their behalf, and this one is not important enough to
justify that.

## Why this exists

Because several claims this system makes are currently unmeasured, and the honest way to
hold an unmeasured claim is to make it measurable rather than to assert a number.

The source material this project descends from carried a specific percentage token saving
in two places with no measurement anywhere in the repository supporting it. That figure
was deleted rather than propagated, and this handler exists so the gap it left can be
filled properly. If you want a number to put in front of a stakeholder, turn this on and
generate a real one from your own usage. An invented benchmark in a tool whose stated
purpose is preventing hallucination would be an unusually poor look.

## What it records

One record per turn: the event name, the repository slug, the session id, the current
pipeline phase read from the newest checkpoint in `memory/sessions/`, a map of tool name
to call count for the turn, and the active hook profile.

Tool counts come from the last two hundred lines of the transcript. This runs on every
`Stop`, and re-parsing a long transcript each time would turn an async nicety into a real
cost.

`session-teardown` appends a matching `session-end` record when a session closes, under
the same environment flag.

Records are appended through `state.appendChained`, which hash-chains each line to the
one before it, so a record removed or edited after the fact is detectable by
`state.verifyChain`.

**What it never records:** file contents, prompt text, response text, or any path outside
the workspace-relative form. The repository is a slug, not a path.

## Action on a hit

None visible. The handler returns allow whether it wrote or not, and every failure path —
an unreadable transcript, a missing checkpoint directory, a failed append — is caught and
swallowed. Telemetry never fails loudly, because a diagnostic that interrupts the work it
is diagnosing is not worth having.

## Recovery / escape

It is off by default, so the escape is the absence of an action.

To turn it off once on: unset `ORCHESTRATOR_TELEMETRY` or set it to anything not in the
enabled list. To remove the hook entirely:
`ORCHESTRATOR_DISABLED_HOOKS=stop:telemetry`, or `ORCHESTRATOR_HOOKS_ENABLED=false`.

To discard what was collected, delete the JSONL file. Deleting it breaks the hash chain
for anything already written, which is the intended behavior — the chain detects
tampering, it does not prevent deletion.

## Honest limits

Nothing is measured unless somebody switches it on, which means that by default this
system's performance claims stay unmeasured. That is the honest state of affairs and this
document is not going to dress it up.

A per-turn tool count is not a token measurement. It tells you what was called, not what
it cost. `scripts/context-bill.py` and `/budget` are the tools for cost;
`measure-discovery-budget.py` measures the discovery footprint.

The two-hundred-line transcript tail undercounts a long turn, silently and by an unknown
amount.

The pipeline phase is read from the most recently modified checkpoint in the workspace,
which is the wrong one when two pipelines are in flight.

Nothing aggregates, summarizes, or reports. There is no dashboard here — the file is raw
JSONL, and turning it into a number is a thing you do yourself.

And it is per machine. Two developers running the same pipeline produce two unrelated
files with no way to combine them that this system provides.

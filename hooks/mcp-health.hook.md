---
name: mcp-health
trigger: PreToolUse
matcher: "mcp__.*"
profiles: [standard, strict]
mode: sync
blocking: true
handler: hooks/runtime/handlers/mcp-health.js
description: Denies calls to an MCP connector already recorded as unhealthy and hands back the fallback that config/tool-registry.json declared for it.
---

# MCP Health Gate

This fires before any tool whose name starts with `mcp__`. It looks up the server that
tool belongs to in the recorded health state and, if that server is currently marked
unhealthy, denies the call and returns the declared fallback instead of spending another
timeout.

It is registered in `hooks/hooks.json` only when an organization enables a
connector. A gate on a surface nobody uses is pure startup cost on every tool call.

## Why this exists

`config/tool-registry.json` declares an `optional` block with a carefully-written
fallback for every connector: emit the stories as Markdown rather than filing them, do
not claim the specs were executed, and so on. That is good design and it is entirely
declarative — nothing in the system probes whether the server is actually up.

So the failure runs like this. A connector goes down mid-pipeline. The phase calls it and
fails with an MCP error. The error-recovery table says "MCP timeout → retry", so the
phase retries, and spends the timeout again. The fallback that somebody thought carefully
about is never reached, because nothing ever decides that it is time to use it.

This hook is the thing that decides. It converts a repeated timeout into a single fast
failure that carries the fallback text, which is what makes the fallback reachable at all.

## What it checks

`serverOf` extracts the server name from the tool name by the `mcp__<server>__<tool>`
convention. If the name does not parse, the hook allows.

Health lives in a JSON file in the state directory, one entry per unhealthy server
holding a failure count, the timestamp it went unhealthy, and a truncated reason.
Entries are written by `markUnhealthy`, which the tool-failure path calls — this hook
records nothing on its own and never probes.

`isUnhealthy` applies two rules. If the entry is older than
`healthPolicy.recheckAfterSeconds` (default 120), the entry is cleared and the call is
allowed, so a server that recovered is retried without anybody clearing state by hand.
If the failure count is below `healthPolicy.markUnhealthyAfterFailures` (default 1), the
call is allowed. Otherwise the server is unhealthy and the call is denied.

## Action on a hit

`permissionDecision: deny`. The reason names the server, how long ago it was marked
unhealthy, how many failures it took, and the recorded reason.

Then one of two things. If `config/tool-registry.json` declares a fallback for that
server, the reason quotes it verbatim and tells the agent to take it. If it does not, the
reason says so and instructs the agent to report the phase as blocked with this reason
rather than retrying — an honest "blocked, here is why" is worth more than a silent
degradation nobody notices.

Either way it closes by stating when the server will be retried automatically, and that
retrying now just spends the timeout again.

## Recovery / escape

**Narrow first.** Wait. The unhealthy mark expires on its own after
`recheckAfterSeconds`, and the next call re-probes for real. Nothing needs to be reset.

**If the server is known good and the mark is stale**, `markHealthy(server)` clears the
entry; deleting `mcp-health.json` from the state directory does the same thing more
bluntly.

**Broad.** `ORCHESTRATOR_DISABLED_HOOKS=pre:mcp:health`, or
`ORCHESTRATOR_HOOKS_ENABLED=false`. Removing the hook does not make the connector work —
it restores the behavior where every call waits out the full timeout.

Tuning is a governance edit: `healthPolicy` lives in `config/tool-registry.json`, which
config protection denies edits to without an override.

## Honest limits

It does not check health. It reads a record that something else wrote, so the first
failure of an outage still costs a full timeout — this hook shortens the second through
tenth, not the first.

The TTL is a timer, not a signal. A server still down after `recheckAfterSeconds` gets
one more real timeout before it is re-marked, and a server that recovered in ten seconds
stays gated for the remainder of the window.

`serverOf` depends on the `mcp__<server>__<tool>` naming convention. A tool name that
does not follow it yields no server, and the hook allows silently.

Health is per server, never per tool or per operation. A connector whose write path is
down and whose read path is fine is treated as entirely unavailable.

The fallback is text handed to the model, not an action taken. Whether the fallback is
actually followed is instruction-following, which this system rates as Moderate control
at best.

And the state file is local. Two sessions on one machine share it; two developers do not
learn from each other's outages.

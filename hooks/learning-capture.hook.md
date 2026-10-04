---
name: learning-capture
trigger: Stop
matcher: ".*"
profiles: [minimal, standard, strict]
mode: async
blocking: false
handler: hooks/runtime/handlers/learning-capture.js
description: Scans the turn's final response for a lesson worth keeping and appends it as a redacted candidate for later triage — never as a memory entry.
---

# Learning Capture

At `Stop`, asynchronously, this reads the assistant's last message and decides whether
the turn contained something worth remembering. If it did, it writes a *candidate* to
`memory/sessions/learning-candidates.jsonl`. It runs inside `stop:dispatcher:async`, so
it never makes the user wait.

It replaces a hook the source material specified with `trigger: onChatResponse`, which
matches no real API. `Stop` is the real event, and it is also the right one: a lesson is
visible once the turn has resolved, not while it is still being written.

## Why this exists

The knowledge an agent produces while working is almost entirely thrown away. The root
cause it found at turn nineteen, the convention it was corrected on, the fix that finally
made the build pass — all of it lives in one transcript, in one repository, and is gone
by the next session. The next agent rediscovers it at the same cost.

Asynchronous is not an optimization here, it is a statement about priority. Capturing a
learning is worth doing and worth exactly zero seconds of the user's attention. It never
blocks, never prompts, and a failure is dropped rather than surfaced.

## Why the reject list matters more than the capture list

Shared memory syncs to every connected repository. A bad entry is not a local mistake —
it is organization-wide replication of a wrong idea, re-injected as context into every
future session in every repository. The bar for writing is therefore high in two separate
ways.

First, the content bar. `REJECT_SIGNALS` throws out anything scoped to a single ticket, a
single branch, or explicitly transient ("for now", "temporarily"), and anything hedged as
"I think", "probably", or "might be". An inference is not a lesson.

Second, the safety bar. Every field goes through `redact.guardFreeText` before it is
written, and there is no flag that skips it. An agent that debugs an auth failure and
writes "regenerated the token to sk-…" would otherwise have replicated a live credential
into every repository in the organization. The same guard rejects prompt-injection
markers, because stored memory is re-read as context later — a resolution note saying
"ignore previous instructions" is a delayed instruction, not data.

## What it captures

Four signal shapes, tested against the last assistant message after the reject list has
had its say: an error recovered ("that fixed it", "now builds"), a pattern discovered
("turns out", "root cause"), a convention corrected ("this repo uses", "convention
here"), and an anti-pattern ("do not … because", "avoid … it breaks").

The record written is a candidate: kind, repo slug, a title taken from the first sentence
that matched, truncated context and resolution, session id, timestamp,
`status: 'candidate'`, `confidence: 0.4`, and the current repository as the only entry in
`seenInRepos`.

That initial confidence sits deliberately below the 0.7 promotion floor, so no single
observation can promote anything however certain the capturing agent sounded.

## Action on a hit

Nothing the user sees. The candidate is appended to
`memory/sessions/learning-candidates.jsonl` and the hook returns allow.

Promotion into `memory/shared/` happens later, through `scripts/memory.py`, which applies
the dedupe and confidence arithmetic and is reviewed with `memory.py review`. A
turn-level regex heuristic should not have direct write access to the organization's
shared brain, and this separation is what keeps that true.

If the redaction guard throws, the handler records a line in `rejected-captures.jsonl`
containing the repository, the kind, the reason, and the session id — and deliberately
not the text that was rejected. You get to know that something was refused and why,
without the refusal itself becoming the leak.

## Recovery / escape

There is nothing to escape; this hook never blocks and never denies.

To stop capture: `ORCHESTRATOR_DISABLED_HOOKS=stop:learning-capture`, or
`ORCHESTRATOR_HOOKS_ENABLED=false`. To discard what was captured, delete
`memory/sessions/learning-candidates.jsonl` — candidates are a queue, not a record.

The redaction guard has no escape, by design, and the same guard is enforced again at the
`scripts/memory.py` write site. See `memory-dedupe.hook.md`.

## Honest limits

It is four regular expressions over one message. It will miss most real learnings, and it
will sometimes capture a sentence that merely reads like one — which is exactly why it
writes a candidate rather than an entry, and why triage exists.

The title is the first signal-matching sentence truncated to 110 characters, so it is
frequently a fragment that reads oddly out of context. Context and resolution are the
same text truncated at different lengths, because a turn-level heuristic has no reliable
way to tell the situation from the fix.

Nothing here deduplicates, scores against existing entries, or checks whether the lesson
is already known. All of that is the promotion path's job.

A failed write is swallowed silently. That is the correct trade for an async nicety, and
it does mean a lost learning leaves no trace at all.

And it reads only the final assistant message. A lesson that appeared mid-turn and was
not restated at the end is not seen.

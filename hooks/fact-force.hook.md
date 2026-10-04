---
name: fact-force
trigger: PreToolUse
matcher: "Edit|Write|MultiEdit"
profiles: [standard, strict]
mode: sync
blocking: true
handler: hooks/runtime/handlers/fact-force.js
description: Denies the first edit or creation of a file in a session until the agent has presented facts it could only have obtained by searching.
---

# Fact-Forcing Gate

This gate runs immediately before an `Edit`, `Write`, or `MultiEdit` executes, on the
first time each file is touched in a session. If the file has not been touched before,
the tool call is denied with a short list of facts that must be presented first. Once
those facts are in the transcript, the same operation retried goes through, and every
later edit to that file in that session passes without comment.

## Why this exists

The architecture this system grew out of enforced grounding at three points and rated
them Strong, Moderate, and Advisory — with the honest admission that the last one
"cannot block." That was true of a runtime that streamed a prompt into a chat window it
did not own. It is no longer true. A `PreToolUse` hook runs before the tool executes and
can deny it, which does not require owning the generation stream — it owns the *action*
stream, and the action stream is where a hallucination stops being a sentence and
becomes an edit. A wrong paragraph is cheap to correct. A wrong edit to a file whose
importers nobody enumerated is not.

The second reason is subtler and is the one worth preserving. Asking a model "are you
sure?" is answered "yes" by construction: the same context that produced the claim is
the context that evaluates it, so self-assessment carries almost no information here.
Forced *retrieval* does. An agent cannot produce the importer list for a file without
actually searching for it, and the act of searching creates the awareness that the
question never did. So this gate does not ask for confidence. It asks for facts whose
presence in the transcript implies the search happened.

## What it checks

The handler allows immediately in four cases: the gate is switched off, the tool is not
an edit or write, no file path is present in the payload, or the path matches an exempt
glob. The default exempt list in `hooks/runtime/lib/gate-state.js` covers tests, build
output, lockfiles, Markdown, and the session and index directories under `memory/` —
paths where "who imports this" carries no signal, so gating them is friction that buys
no investigation.

A `Write` to a path that does not exist yet is classified as a creation; a `Write` over
an existing file is an edit wearing a `Write`'s clothes, and the importer question still
applies to it.

For an edit, the four demanded facts are the importers of the file, the exported symbols
the change affects with `file:line` for each, the field names and shapes of any
persisted data it touches, and the user's current instruction quoted verbatim. For a
creation, the first three become: what will call the new file, confirmation that nothing
existing already serves the purpose, and which manifest entry authorizes the path.

Fact 4 is the same in both and is deliberately unrelated to the file. It is the drift
check: forty turns into a session, the goal being executed and the goal that was given
are not reliably the same thing, and nothing else in this system tests for that.

## Action on a hit

`permissionDecision: deny`, with the fact list and both recovery paths as the reason —
the reason string is the only channel a gate has, so it says what to do rather than only
what went wrong. After three full blocks in one session the denial collapses to a single
line carrying an ordinal. An identical eight-line block repeated ten times burns context
and, worse, becomes wallpaper the model learns to pattern-match past; a gate that is
ignored is a gate that is not there.

Compliance is unusually cheap here, and that is not accidental. In a generic repository
fact 1 means a manual tree walk; this system maintains a structural graph, so the answer
is `python scripts/graph.py importers <file>`. The handler probes for that script and
falls back to suggesting Grep or Glob when the index is not present.

## Recovery / escape

**Narrow first.** Add a path glob to `ORCHESTRATOR_GATE_EXEMPT_GLOBS` to skip
first-touch checks for that path alone. Every other gate stays on, including this one
everywhere else.

**Broad, when setup or repair work is genuinely blocked.** Run with
`ORCHESTRATOR_GATEGUARD=off`, or add `pre:edit-write:fact-force` to
`ORCHESTRATOR_DISABLED_HOOKS`. `ORCHESTRATOR_HOOKS_ENABLED=false` turns off the whole
runtime.

The order matters. A gate that offers only "turn it all off" gets turned all off,
permanently, the first time it is inconvenient. Offering a scalpel before the sledgehammer
is what keeps the gate installed.

## Honest limits

It cannot tell a retrieved fact from an invented one. Nothing here parses the agent's
answer or checks that the named importers exist; the gate buys the search, not the
truth. Grounding of the answer itself is the `grounding-guard` skill's job, and that
skill is candid that its own questions are self-assessment.

It fires once per file per session. The tenth edit to a file is unguarded, which is the
deliberate trade that keeps the tool usable — and it does mean a session that drifts
after its first edit drifts unobserved.

It sees one tool call, never a plan. A refactor across twelve files is twelve
independent first touches, and no part of this notices that they are one change.

It does not cover writes that do not go through the edit tools. A heredoc, a `sed -i`,
or a shell redirect through `Bash` never reaches this matcher; those are the destructive
gate's surface, and that gate is looking for something else entirely.

The handler treats `NotebookEdit` as an edit tool, but the registered matcher is
`Edit|Write|MultiEdit`, so notebook edits do not currently reach it.

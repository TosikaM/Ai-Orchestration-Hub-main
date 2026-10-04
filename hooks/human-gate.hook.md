---
name: human-gate
trigger: Stop
matcher: ".*"
profiles: [minimal, standard, strict]
mode: sync
blocking: true
handler: hooks/runtime/handlers/human-gate.js
description: Blocks the end of a turn while a pipeline phase has a gate artifact on disk and no matching human verdict file.
---

# Human Gate

At `Stop`, this scans `memory/sessions/` for gate artifacts that have no verdict beside
them. If it finds any, the turn is blocked. The agent cannot finish by asserting that it
stopped and waited; it has to actually wait for a file that only a human writes. It runs
in `stop:dispatcher:sync` alongside the citation guard.

## Why this exists

Three pipeline phases are declared `humanGate: true` in `config/pipeline-graph.json`, and
the entire implementation was a toast notification saying the phase "needs human
approval". The protocol text instructed the model to post the summary, update the status,
stop, and wait — an instruction enforced by nothing.

Instruction-following is precisely the class of control this system's own grounding
architecture rates as Moderate, and a Moderate control on the step where a human is
supposed to take responsibility is the wrong strength. If the gate can be satisfied by
the agent deciding it has been satisfied, it is not a gate; it is a request with
ceremony.

The insight is the same one behind the fact-forcing gate: you do not need to own the
generation stream to own the action stream, and *stopping is an action*. `Stop` is a
hook, a hook can block, so the gate becomes real.

## What it checks

The file protocol is the point.

```
memory/sessions/<pipelineId>.gate-<phase>.md      the artifact to review
memory/sessions/<pipelineId>.gate-<phase>.json    the verdict
```

Every `.gate-<phase>.md` with no matching `.json`, or with a `.json` that carries no
`verdict` field, is pending. A verdict of `changes-requested` counts as answered — the
agent should act on it, not keep waiting.

The verdict is a JSON file rather than an entry in a database, so
`python scripts/pipeline.py approve <pipelineId> <phase>` works identically to the view
plane's gate panel. The panel is a nicety over a file protocol, never a dependency:
anyone on Linux, in a terminal, or in a different editor is fully served.

The handler allows immediately when `ctx.stopHookActive` is set. If a previous `Stop`
hook already blocked this turn, blocking again is an infinite loop.

## Action on a hit

`decision: block` with a reason, which forces the agent to keep working rather than
ending the turn. The reason names each pending pipeline and phase with the relative path
of its artifact, then gives three steps in order of preference:

1. If the artifact is not yet complete, finish writing it. A gate with a thin artifact
   trains the reviewer to approve without reading, which defeats every gate in the
   pipeline — including the ones that would have caught something.
2. Tell the user the gate is open, summarize what they are approving in three lines, and
   stop asking for anything else.
3. The user approves in the gate panel, or from a terminal with
   `pipeline.py approve` / `pipeline.py request-changes --note "..."`.

It closes with the sentence that carries the whole design: do not write the verdict file
yourself. A gate the agent can clear is not a human gate.

## Recovery / escape

**Narrow first, and it is the intended path.** Answer the gate. Approve or request
changes through `scripts/pipeline.py` or the gate panel; the verdict file appears and the
next `Stop` passes.

**If the gate is stale** — an artifact left behind by an abandoned pipeline — write a
verdict for it or remove the artifact. Either clears the block, and both are visible acts
on disk rather than a setting.

**Broad.** `ORCHESTRATOR_DISABLED_HOOKS=stop:human-gate`, or
`ORCHESTRATOR_HOOKS_ENABLED=false`. Note that no profile removes this hook: it is in all
three, because a lighter profile should mean less friction, not fewer approvals.

## Honest limits

The gate is a file check, and the agent can write files. Nothing here prevents an agent
from writing the verdict JSON itself; the instruction not to is an instruction, with all
the weakness this document has already ascribed to instructions. What the gate genuinely
guarantees is narrower and still worth a great deal: clearing it requires a deliberate,
auditable write to a named file, rather than a sentence in prose claiming that approval
happened. A wrong action leaves evidence. A wrong assertion does not.

`stopHookActive` is a loop guard, not a queue. If another `Stop` hook blocked first, this
one steps aside for that turn, so a gate that opens in the same turn as another block can
go unannounced until the next `Stop`.

It sees only this workspace's `memory/sessions/`. A gate belonging to a pipeline running
from another checkout is invisible.

It checks for the presence of a `verdict` field, not its meaning. Any non-empty verdict
value clears the block, including one written in error.

And it cannot judge the artifact. A gate blocked on a two-line summary blocks exactly as
firmly as one blocked on a thorough review document; step 1 of the message exists because
the hook can ask for a better artifact but cannot require one.

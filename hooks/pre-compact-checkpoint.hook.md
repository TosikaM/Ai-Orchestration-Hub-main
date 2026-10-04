---
name: pre-compact-checkpoint
trigger: PreCompact
matcher: ".*"
profiles: [minimal, standard, strict]
mode: sync
blocking: false
handler: hooks/runtime/handlers/pre-compact-checkpoint.js
description: Writes the in-flight pipeline checkpoint to disk before the context window is compacted, and tells the agent to re-enter at the recorded phase afterwards.
---

# Pre-Compact Checkpoint

This fires at `PreCompact`, the one moment where the runtime knows the window is about to
be rewritten and can still act. It finds the most recently modified in-flight pipeline
checkpoint in `memory/sessions/`, stamps it, writes it atomically, and tells the agent
what it will need to re-read on the other side.

## Why this exists

This closes a real defect, not a missing feature.

The pipeline service writes a checkpoint on phase transitions, and the design note beside
it says checkpoints survive a window reload where plain in-memory state does not. That is
true for a reload. Compaction quietly falsifies it. A long `implement` phase that
triggers a compaction loses everything since the last gate, because the only durable
write happens at a boundary the phase has not reached yet — and the longer the phase, the
more likely compaction is and the more there is to lose. The two probabilities move
together in exactly the wrong direction.

Writing the checkpoint here costs milliseconds and converts "lost the phase" into
"resumed at the phase."

## What it does

It reads `memory/sessions/*.checkpoint.json`, takes the newest by modification time, and
stops if the checkpoint is missing, unparseable, or already marked `complete` or
`abandoned` — a finished pipeline needs no rescue.

Otherwise it increments a `compactions` counter, records `lastCompactedAt`, and writes a
`compactionNote` into the file itself stating that anything the phase learned which is
not written into this file or into the repository is gone after compaction, and that the
agent should re-read before assuming. The note lives in the artifact rather than only in
the transcript, because the transcript is the thing about to be summarized away.

The write goes through `state.writeJsonAtomic`, so a compaction that happens to coincide
with another writer cannot leave a half-written checkpoint.

## Action on a hit

A `systemMessage` — an inform. It names the pipeline and the phase it was in, gives the
workspace-relative path of the file that was written, and states the instruction that
matters most: after compaction, re-read that file before continuing, and do not restart
the pipeline — re-enter at the recorded phase.

That last sentence exists because the observed failure after a compaction is not doing
nothing; it is starting over. An agent with a summarized transcript and a half-remembered
goal will happily re-run a phase whose outputs already exist.

## Recovery / escape

Nothing here denies, so there is nothing to escape from in the usual sense.

If the checkpoint written was the wrong one — two pipelines in flight, and this one
picked the more recently touched — the fix is to read the correct
`memory/sessions/<pipelineId>.checkpoint.json` directly and re-enter from that.

To disable: `ORCHESTRATOR_DISABLED_HOOKS=pre:compact:checkpoint`, or
`ORCHESTRATOR_HOOKS_ENABLED=false`. The consequence is the defect described above,
restored.

## Honest limits

It saves the checkpoint file, not the reasoning. Everything the phase worked out and
never wrote down is still lost. This hook makes that fact explicit in the note rather
than fixing it, because there is nothing here that could fix it — the durable record has
to be written by the phase, at the time, and no hook can retroactively make one exist.

It picks the most recently modified checkpoint, which is a heuristic. With two pipelines
in flight in one workspace it can stamp the wrong one, and it will not say so.

It only fires when the harness raises `PreCompact`. A context overflow handled some other
way, a crashed process, or a session closed mid-phase gets no checkpoint from this hook.

It reads this workspace's `memory/sessions/` only, and falls back to
`paths.workspaceRoot()` when the payload carries no `cwd` — a session started elsewhere
may find nothing.

And the instruction to re-enter rather than restart is an instruction. Nothing enforces
it.

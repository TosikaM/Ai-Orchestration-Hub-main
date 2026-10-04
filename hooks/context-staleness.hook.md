---
name: context-staleness
trigger: Stop
matcher: ".*"
profiles: [standard, strict]
mode: async
blocking: false
handler: hooks/runtime/handlers/context-staleness.js
description: Marks the repository context file stale when enough source files have changed since it was written, without refreshing it mid-task.
---

# Context Staleness Detector

At `Stop`, asynchronously, this compares the modification time of
`.github/orchestrator-context.md` against the source tree. If enough files have changed
since the context file was written — or if a new module directory has appeared — it
writes a staleness marker into the state directory. It runs in `stop:dispatcher:async`
and says nothing to the user during the turn.

## Batched at Stop, not per save

The original specification gave this `trigger: onSave`, an invented event that
corresponds to no real API. Even if it had existed, per-save is the wrong granularity:
ten edits in one turn would mean ten staleness evaluations, each walking the same tree
and writing the same marker. Running once at `Stop`, over the whole turn's edits, is the
identical signal for a tenth of the work. `Stop` is both the real event and the better
one.

## Why this exists

`.github/orchestrator-context.md` is the document every analysis reasons from — the layer
map, the entry points, the conventions. It is generated once and then quietly rots. The
failure is not that it becomes wrong all at once; it is that it stays *mostly* right,
which is worse. An agent reading a layer map that is ninety percent accurate has no way
to know which ten percent it is standing on, and the parts that changed most recently are
precisely the parts most likely to be under discussion.

Session bootstrap already reports the context file's age. Age is a poor proxy for
staleness: a file untouched for a month in a repository nobody committed to is fine. This
hook measures the thing age is standing in for.

## What it checks

It walks the workspace to a depth of six, skipping `node_modules`, `.git`, build output
directories, virtualenvs, `__pycache__`, `memory/`, and dot-directories other than
`.github`. It counts files with a source extension — the TypeScript and JavaScript
family, C#, Python, Java, Kotlin, Go, Rust, Ruby, PHP, Vue, Svelte, Terraform, SQL —
whose mtime is later than the context file's, and bails early once the count passes three
times the threshold, since the answer cannot change after that.

Two signals make the context stale: more than twenty changed source files, or any
directory created after the context file was written. The second one is worth its own
branch — a new module or feature directory is a structural change the layer map cannot
contain, and one new directory matters more than twenty edits inside existing ones.

## Action on a hit

It writes `context-staleness.json` into the repository's state directory: the repo slug,
the context file path, when the context was written, the changed-file count, the new
module directory if there was one, the detection time, a human-readable reason, and an
explicit `action` field reading "suggest a refresh at the next phase boundary; do not
auto-refresh mid-task."

Then it returns allow. Nothing is shown, nothing is blocked.

**Passive by design.** It marks staleness and does not regenerate anything. Refreshing a
context file underneath somebody who is mid-task is worse than letting them work against
a slightly stale one: the refresh rewrites the exact document they were reasoning from,
and they have no way to tell that it changed under them. The marker lets the orchestrator
refresh at a phase boundary instead, which is the moment where a rewrite is expected and
where the cost of re-reading is already being paid.

## Recovery / escape

Nothing blocks, so there is nothing to recover from.

To clear a marker, refresh the context file — `/orchestrator-init` regenerates it, and a newer mtime
makes the next run find nothing. Deleting the marker file works too and is what you want
if the change was a formatter run rather than a real one.

To disable: `ORCHESTRATOR_DISABLED_HOOKS=stop:context-staleness`, or the `minimal`
profile, which does not include this hook, or `ORCHESTRATOR_HOOKS_ENABLED=false`.

## Honest limits

Modification time is not change. A branch switch, a checkout, a formatter run, or a
dependency update touches many files without moving the architecture one inch, and every
one of those counts here. Expect false staleness after any bulk operation.

It counts files, not relevance. It does not read the context file, so twenty changes in
an area the context file never described count exactly the same as twenty in the area it
does.

`birthtimeMs` is not reliable on every filesystem. The new-module signal can be missed
entirely, and on some platforms it can fire for a directory that was merely moved.

The depth limit of six and the skip list make parts of a large monorepo invisible, and
the early bail means the reported count is a floor rather than a total once it is high.

The threshold is a constant in the handler, not a configured budget. Twenty is a judgment
call that has not been fitted to anything.

And the marker is a note on disk. Whether anyone reads it at the next phase boundary is
outside this hook.

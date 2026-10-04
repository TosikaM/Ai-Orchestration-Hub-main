# The View Plane

A deliberately small VS Code extension that **reads** the orchestrator's state files and
shows them. It runs no pipeline, loads no skills, routes no commands, and syncs nothing.

The directory is called `view/` rather than `extension/` on purpose. The name is the
clearest available statement of the boundary, and it makes "does this belong in the view
plane?" a question somebody actually asks before adding a file — which a directory called
`extension/` never prompts.

## Where this fits

The system has three planes.

| Plane | What it is | Where it lives |
|-------|-----------|----------------|
| Content | The Markdown brain: agents, skills, commands, contexts, memory | `agents/`, `skills/`, `commands/`, `contexts/`, `memory/` |
| Runtime | Claude Code itself, via a plugin that contributes skills, agents, hooks and CLI scripts | `.claude-plugin/`, `hooks/`, `scripts/` |
| View | This extension. Reads state files, owns no orchestration | `view/` |

## What this deliberately is not

An earlier design shipped a VS Code extension as the runtime. It had to re-implement
skill loading, slash-command routing and content sync by hand, and its own architecture
document named the central limitation: it "does not own the generation stream" and
therefore "cannot block". A quality gate that cannot block is a suggestion with a
progress bar.

Under Claude Code a `PreToolUse` hook returns a permission decision of `deny`, so the
system owns the **action** stream instead — which is where a hallucination stops being a
sentence and becomes an edit. Roughly five of the twelve former services turned out to be
re-implementations of platform primitives, so they were deleted rather than ported, and
about three thousand lines of TypeScript went with them:

- the chat participant — Claude Code is the chat surface
- the skill loader — the plugin contributes skills; the host loads them
- the hub sync service — `/plugin` upgrades handle distribution, and `simple-git` left
  with it, which is why this extension has **no runtime dependencies at all**
- the token budgeter — enforced by a hook, where it can actually refuse
- the context generator — `scripts/context-gen.py`, callable from anywhere
- the write side of memory, pipeline, cross-repo and telemetry — all of it CLI and hooks

What is left is the part a tree does better than a transcript.

## The three things it is genuinely good at

**1. Pipeline state at a glance.** The pipeline is a DAG: `review` and `test` are
siblings that run at the same time, `deploy` waits for both, phases carry scores against
thresholds, and two phases stop dead until a human writes a verdict. A chat transcript
renders that as prose spread over forty turns, so "what is running, what is blocked, and
on whom" is answered by scrolling and reconstructing. The tree answers it by existing.

**2. Browsing shared memory.** `python scripts/memory.py search "<query>"` is the right
tool when you know what you are looking for. Most of the value of a memory store is in
the case where you do not — noticing that four anti-patterns have piled up around one
subsystem, or that an instinct you disagree with has been reinforced in three
repositories. That is found by looking, not by querying.

**3. Giving a human gate an actual artifact to approve.** Three pipeline phases are
human-gated, enforced by a Stop hook that refuses to let the session end while a gate
artifact exists with no verdict beside it. The agent genuinely cannot clear its own gate.
What a human needs at that moment is the artifact in front of them and two buttons, while
the session is still blocked on it. That is the gate panel.

## The one write, and why it is only one

`scripts/validate-structure.py` greps `view/src/**/*.ts` for `writeFileSync`,
`appendFile`, `mkdirSync`, `rmSync`, `unlinkSync` and friends, and fails the build unless
the file containing one also contains the literal marker `gate-verdict-write`. Exactly one
file does: `src/providers/gateReview.ts`, which records a human's verdict as
`memory/sessions/<pipelineId>.gate-<phase>.json`.

That exception exists because a human verdict cannot originate anywhere else. Everything
else this window could conceivably write already has a home in the runtime plane, and the
check is there so that adding a second write requires arguing for it in a pull request
rather than doing it quietly on a Friday.

**The panel is a nicety over a file protocol, never a dependency.** The verdict is a JSON
file, and

```
python scripts/pipeline.py approve <pipelineId> <phase>
python scripts/pipeline.py request-changes <pipelineId> <phase> --note "..."
```

write the same file. Anyone on Linux, in a terminal, in a different editor, or on a
machine where this extension is not installed is fully served.

One asymmetry worth knowing: the CLI writes the verdict **and** folds it into the
checkpoint, marking the phase complete and activating whatever the DAG says is next. The
panel writes only the verdict, because that is the only file it may write. The verdict is
what releases the blocked session — the Stop hook reads the verdict file, not the
checkpoint — but the checkpoint's mirrored status catches up on the next `pipeline.py`
run. The pipeline tree reconciles the two at read time and labels the gap, so the state
is visible rather than merely inconsistent. If you want both in one step, use the CLI.

## What it reads

| Source | Used for |
|--------|----------|
| `memory/sessions/*.checkpoint.json` | the pipeline tree |
| `memory/sessions/*.gate-<phase>.md` / `.json` | gate artifacts and verdicts |
| `memory/sessions/*.band.json` | cross-repo band progress |
| `memory/shared/*.md` | the memory tree |
| `.github/agents/*.agent.md`, or `agents/` | the agents tree |
| `~/.orchestrator/state/connected-repos.json` | the connected-repos tree |
| `~/.orchestrator/telemetry.jsonl` | the optional dashboard section |
| `.github/orchestrator-install.json` | activation, and "is this repo connected" |

Two honest limits in that table.

The agents tree reads files on disk, and under the plugin model the agents ship **inside
the plugin**, not in the consumer repository. So it can see them in exactly two
situations: the open folder is the hub checkout, or somebody ran `connect-repo.ps1
-Vendor` to place a copy in `.github/agents/`. In every other case the tree says the
agents are in the plugin and it cannot read them, rather than showing an empty list —
because an empty list reads as "this repo has no agents", which is false. It has ten, and
they are loaded and working.

The telemetry ledger is local-only and off unless `ORCHESTRATOR_TELEMETRY` is set. When
it is absent the dashboard says "not recorded" rather than "0 events", because those are
different facts and only one of them is true.

A third worth stating: the connected-repos tree reads the **live** machine-scoped
registry, the same file `cross-repo.py list` reads. The hub also carries a committed
declaration at `registry/connected-repos.yml`, nothing reconciles the two automatically,
and so a repo declared there but never connected on this machine will not appear in the
tree. That is a known gap in the system rather than a rendering fault here.

## Settings

All settings live under the prefix `aiorchestrator`, all lowercase.

That is worth a paragraph rather than a line. A prior version declared its settings as
`aiorchestrator.*` in `package.json` and read them back as
`getConfiguration('aiOrchestrator')` — capital O — in nine separate call sites. VS Code
does not raise an error for a configuration section that does not exist; it hands back an
empty section, and `get(key, fallback)` on an empty section returns the fallback. Every
one of those nine reads therefore returned the default, silently. Nothing failed, nothing
logged, and the settings UI looked perfectly correct because the UI reads `package.json`
rather than the code. It was the highest-impact defect in the source material this
project was rebuilt from, and it was invisible precisely because the failure mode of a
wrong section name is "everything keeps working, at the defaults".

The fix is structural rather than a spelling correction. `SETTINGS_PREFIX` in
`src/shared/constants.ts` is the only place the section name is written, `setting()` in
the same file is the only function that calls `getConfiguration`, and the keys are
constants too. A typo now breaks compilation instead of behaviour.

| Setting | Default | What it does |
|---------|---------|--------------|
| `aiorchestrator.stateHome` | `""` | Override the machine-scoped state directory. Empty falls back to `ORCHESTRATOR_HOME`, then `~/.orchestrator`. |
| `aiorchestrator.refreshOnFileChange` | `true` | Refresh trees when `memory/sessions/**` changes. |
| `aiorchestrator.pipeline.showCompleted` | `true` | Show finished and abandoned pipelines. |
| `aiorchestrator.memory.maxEntriesPerCategory` | `50` | Cap entries listed per memory category. |
| `aiorchestrator.gateReview.confirmApprove` | `true` | Confirm before recording an approval. |
| `aiorchestrator.dashboard.showTelemetry` | `false` | Include the telemetry summary. |

## Build and install

Requires Node 18 or newer for the build tooling. Nothing is required at runtime.

```
cd view
npm install          # dev dependencies only — this extension has no runtime deps
npm run typecheck    # tsc --noEmit, strict
npm run bundle       # esbuild -> out/extension.js, the file that ships
npm run package      # produces algoworks-ai-orchestrator-view-3.1.0.vsix
code --install-extension algoworks-ai-orchestrator-view-3.1.0.vsix
```

`npm run compile` runs `tsc` with emit, producing unbundled JavaScript under `out/` for
step debugging. `npm run bundle` overwrites `out/extension.js` with the single bundled
file, and that is what `vsce package` ships — `.vscodeignore` keeps everything else out.

Press `F5` in this folder for an Extension Development Host with the extension loaded.

The extension activates on `workspaceContains:.github/orchestrator-install.json`, so it
stays dormant in repositories that are not connected to the orchestrator.

Note for anyone editing the config files: `tsconfig.json` here contains no comments, even
though TypeScript would accept them. `scripts/validate-structure.py` parses every `.json`
in the repository with a strict JSON parser, and a JSONC comment fails that check with an
error message that points at the file rather than at this rule.

## Installing the rest of the system

The view plane is optional. The orchestrator itself is the plugin:

```
/plugin marketplace add abhishek-narula-algoworks/Ai-Orchestration-Hub
/plugin install orchestrator@algoworks
```

Requires Claude Code 2.1 or newer.

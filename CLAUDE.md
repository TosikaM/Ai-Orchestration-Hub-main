# CLAUDE.md

Instructions for Claude Code working **on** this repository. This file loads in every
session here, so it stays short.

## What this project is

The AI Orchestrator Hub: a centralized, technology-agnostic AI SDLC orchestrator,
distributed as a Claude Code plugin. It contributes 17 skills, 10 agents, 28 commands and
16 hooks, and its distinguishing capability is that a `PreToolUse` hook can return
`permissionDecision: "deny"` — so it owns the action stream rather than the generation
stream. Content is Markdown; enforcement is Node; the CLIs are Python.

## The three planes

| Plane | What it is | Rule |
|---|---|---|
| **Content** | `agents/` `skills/` `commands/` `prompts/` `contexts/` `instructions/` `memory/` `knowledge/` | Inert Markdown. Generated from `content-src/`. |
| **Runtime** | `.claude-plugin/` `hooks/runtime/` `scripts/` `lib/` | Owns every decision. |
| **View** | `view/` — a slim VS Code extension | Reads state files. Writes exactly one thing: a human-gate verdict. `check_plane_separation` fails the build otherwise. |

---

## THE GENERATED-CONTENT RULE

**`agents/`, `skills/*/SKILL.md`, `commands/`, `prompts/`, `contexts/` and
`instructions/` are GENERATED.** Every one of those files carries a banner immediately
after its frontmatter saying so.

Edit the `.tmpl` under `content-src/`, or the shared block under `content-src/preamble/`,
then run:

```
python scripts/gen-content.py
```

Never hand-edit a file carrying the generated banner. The edit is a fork of its source
that nobody will notice: the next render silently discards it, and until then the file and
its template disagree with no error anywhere. `scripts/gen-content.py --check` is what
makes that a build failure rather than a slow divergence.

The same rule governs merge conflicts. **Never resolve a conflict on a generated file by
accepting either side.** Resolve on the `.tmpl` and on `content-src/preamble/`,
regenerate, and stage the result. Accepting one side's render silently discards the other
side's template change, and because the render looks plausible, review does not catch it.

Hand-authored, not generated: `skills/*/commands/*.md`, `skills/*/references/*.md`,
everything under `config/`, `hooks/runtime/`, `lib/`, `scripts/`, `evals/`, `templates/`
and `view/`.

---

## Golden rules

**G1 — Do not invent files.** The manifest is `scripts/_lib.py`: `AGENTS`, `SKILLS`,
`COMMANDS`, `CONTEXTS`, `HOOKS`. A path not authorized by one of those lists does not get
created. If a new file is genuinely needed, add it to the list in the same change, so it is
a reviewable line in a diff rather than a directory that grew.

**G2 — Preserve exact casing and extensions.** `SKILL.md` is uppercase.
`*.agent.md`, `*.hook.md`, `*.prompt.md`, `*.instructions.md`, `*.md.tmpl` are exact. The
loader is case-sensitive on Linux and in CI even when your filesystem is not, so a file that
works locally can be invisible in the pipeline.

**G3 — YAML frontmatter is mandatory** on every agent, skill, command, prompt and context.
It must start at byte 0 — the generated banner goes *after* the closing `---`, never before
it, because every parser expects the frontmatter first.

**G4 — No organization-identifying string outside `hub.config.json` and `overlays/`.** The
CI grep gate fails the build on it. This is what makes the hub reusable by another team
without a fork, and it works because exactly one file is exempt from the scan. Read the org
name through `scripts/_lib.py:org_id()` or `lib/config.js`; never type it.

**G5 — Never state a fact about this codebase without a `file:line` citation.** Not "the
budget is 4,000 bytes" but "`config/token-budgets.json:9` sets it to 4,000." If you have
not opened the file in this session, you are recalling a pattern, not reporting a fact —
say which one you are doing.

**G6 — If a value is not specified, stop and ask.** Do not pick a plausible default and
proceed. A guessed ceiling, a guessed profile name, a guessed path becomes load-bearing the
moment it is written down, and the next reader cannot tell it from a decision. An honest
"not found" outranks a plausible guess; that is a value here, not a formality.

---

## Before any commit

```
python scripts/gen-content.py                  # always
python scripts/measure-discovery-budget.py     # only if any frontmatter changed
python scripts/validate-structure.py           # always — must exit 0
```

Order matters. Running `validate-structure.py` against stale generated content produces
failures that describe the wrong problem, and a contributor who chases those learns to
distrust the validator.

If you edited a hook handler, also run `node --check` on it. A hook that will not parse does
not announce itself: Claude Code runs it, Node exits non-zero, the hook contributes no
decision, and the session continues exactly as though the gate had allowed the action.

## Running things locally

`package.json` wraps the common CLIs; the Python form underneath is identical.

| Task | Command |
|---|---|
| Full local build — generate, then validate | `npm run build` |
| Validate only — must exit 0 | `npm run validate` |
| Context bill · fail over budget | `npm run bill` · `npm run bill:check` |
| Discovery budget: re-measure · verify | `npm run budget` · `npm run budget:check` |
| Diagnose the install in this repo | `npm run doctor` |
| Gate-tier evals | `npm run evals:gate` |
| **One eval by id** | `python evals/eval-runner.py --case eval-003` |
| Every case in every tier | `python evals/eval-runner.py --all` |

`evals/eval-runner.py` drives the real `claude` CLI headlessly, so it needs Claude Code on
the PATH and it spends tokens on every run. The `gate` tier is diff-selected by default —
`--no-diff` runs the whole tier regardless of what you touched. Which tier a case belongs
in is decided by `tierRule` in `evals/evals.json`, not by preference.

The VS Code extension has its own toolchain and the root scripts do not cover it: from
`view/`, `npm run typecheck`, `npm run bundle` (esbuild), `npm run package` (vsce).

## Testing a hook without Claude

Because a failing hook contributes no decision, "the edit went through" cannot distinguish
a broken handler from an unwired one. Exercise the handler directly and the two separate:

```bash
export ORCHESTRATOR_PLUGIN_ROOT="$PWD"
echo '{"session_id":"t","tool_name":"Edit","tool_input":{"file_path":"src/x.ts"}}' \
  | node hooks/runtime/run.js pre:edit-write:fact-force
```

A `permissionDecision: "deny"` on stdout means the runtime is fine and only the wiring is
in question. The hook ids and the three profiles are in `hooks/runtime/registry.json`.
When a gate blocks setup or repair work, the escape hatches are `ORCHESTRATOR_GATEGUARD=off`,
`ORCHESTRATOR_DISABLED_HOOKS`, and `ORCHESTRATOR_GATE_EXEMPT_GLOBS` for a single path.

Two things make this harness confusing if you do not expect them. **The gates read your own
tool call**, so a payload containing a recursive-delete literal trips `pre:bash:destructive-gate`
on the command carrying it and you never reach the handler; compose such a string at runtime,
or accept the denial as the proof it is. And **`pre:edit-write:fact-force` fires once per
file per session**, so a second run with the same `session_id` prints nothing and looks
broken — pass a fresh id when you mean to test it again.

## Trying a change as an installed plugin

```
/plugin marketplace add ./
/plugin install orchestrator@algoworks
```

The trailing slash is required; a bare `.` is rejected as *"Invalid marketplace source
format"*. Installing **copies** the repository into `~/.claude/plugins/cache/`, so it is a
snapshot rather than a link — edits in the working tree do not reach the running plugin
until you reinstall, and a change that appears to have no effect is usually this.

`claude plugin update` will not rescue you: it compares versions, and a content-only change
leaves the version untouched, so it reports *"already at the latest version"* and copies
nothing. Uninstall and reinstall, then diff a file you changed against the cached copy to
confirm the refresh actually happened rather than assuming it did.

`claude plugin validate .` checks the manifests without installing anything. The two
warnings about `_componentDeclaration` and `_mcpServersNote` are expected — those keys are
deliberate documentation that Claude Code ignores at load time.

## The ratchet protocol

Skill frontmatter (`name` + `description`) is parsed in every session in every repository
before the user types. It is budgeted at 240 bytes per skill, 4,000 aggregate.

- **Real growth** — re-measure and commit the `derivation` block **in the same commit**, so
  the cost is a visible line in the diff.
- **Accidental growth** — do *not* re-measure. Fix the frontmatter; trigger text, `USE FOR`
  and `NOT FOR` belong in the `## Routing` body.
- **A reduction landed** — re-measure immediately so the ceiling ratchets **down** and the
  win is locked in.

`measure-discovery-budget.py --check` fails CI when the recorded value and reality disagree.

## Where things live

| Need | Look in |
|---|---|
| The inventories, the frontmatter parser, the discovery measurement, the redaction scan | `scripts/_lib.py` |
| Token ceilings, priority order, the derivation block | `config/token-budgets.json` |
| The SDLC DAG, gates, human gates, checkpoint paths | `config/pipeline-graph.json` |
| Which hook serves which event, profiles, dispatchers | `hooks/runtime/registry.json` |
| Which hooks Claude Code actually registers | `hooks/hooks.json` |
| Org identity, hub version, plugin install coordinates | `hub.config.json` |
| Secret patterns, tiers, suppressions, sink polarity | `config/redaction-patterns.json` |
| Stack detection and per-stack commands | `config/stack-mappings.json` |
| What "valid" means for everything else | `scripts/validate-structure.py` |
| Memory tiers, confidence arithmetic, promotion rule | `memory/README.md` |
| Why the runtime is a plugin and not an extension | `docs/adr/0001-claude-plugin-as-runtime.md` |
| Adding a skill, agent, stack or memory entry | `CONTRIBUTING.md` |

## Encoding traps on this platform

**Every `.ps1` file must be saved as UTF-8 *with* a BOM.** This is not a style
preference; it is a correctness requirement, and CI gates it.

Windows PowerShell 5.1 — the default shell here — reads a BOM-less `.ps1` as
Windows-1252 rather than UTF-8. This codebase uses em-dashes throughout, and an em-dash
is UTF-8 `E2 80 94`; read as ANSI, the trailing `94` becomes `U+201D`, a right double
quotation mark, which PowerShell treats as a string delimiter.

The failure is deliberately worth describing, because it wastes an afternoon otherwise:
the parser reports *"the string is missing the terminator"* and *"missing closing `}`"*
at lines nowhere near the em-dash, it only bites when an em-dash lands inside a
double-quoted string (the same character is harmless in a comment), and it **cannot
reproduce on Linux or in PowerShell 7**, which is where people naturally go to debug it.

If you write or edit a PowerShell script, re-save it with a BOM:

```powershell
Get-ChildItem scripts -Filter *.ps1 | ForEach-Object {
  $t = [IO.File]::ReadAllText($_.FullName)
  [IO.File]::WriteAllText($_.FullName, $t, (New-Object Text.UTF8Encoding $true))
}
```

Two related 5.1 constraints, both of which produce equally misdirected parse errors:
a method chain does **not** continue over a trailing dot across lines, and a
`[MatchEvaluator]{ ... }` scriptblock cast is unreliable. Use an explicit loop and
`String.Replace` instead — `scripts/connect-repo.ps1` shows the shape.

**The rule inverts for JSON: a state file must be written *without* a BOM.** In Windows
PowerShell 5.1 `Set-Content -Encoding utf8` emits one anyway, so a PowerShell-written
`.json` carries `EF BB BF` and every strict reader rejects it. Write it explicitly instead:

```powershell
[IO.File]::WriteAllText($path, $json, (New-Object Text.UTF8Encoding $false))
```

This cost real time once already. `connect-repo.ps1` wrote `orchestrator-install.json`
with a BOM, `json.load` raised on byte 0, and `doctor` reported *"no install state"* while
the file sat in place at the exact path it named. As with the `.ps1` trap, PowerShell 7
and Linux emit no BOM, so it cannot reproduce where you would naturally go to debug it.

## Readers fall back silently — check the file parses before believing them

`scripts/_lib.py:read_json` returns its `default` on **any** failure, and `readJson` in
`lib/config.js` and `lib/state.js` return `null`/`fallback` the same way. A file that is
present but unparseable is therefore indistinguishable from one that is absent, and the
message you get names absence. Before trusting "not connected", "not found", or a default
that seems wrong, parse the file yourself.

Keep new readers BOM-tolerant — `encoding="utf-8-sig"` in Python, `.replace(/^\uFEFF/, '')`
before `JSON.parse` in Node — so a BOM downgrades to a non-event rather than a phantom
absence.

## The repo context file is a guess, not a measurement

`.github/orchestrator-context.md` is generated by matching indicators in
`config/stack-mappings.json`, and those indicators are OR-ed: for `dotnet-cqrs`, a
`*.csproj` containing MediatR **or** a directory named `Commands` **or** one named
`Handlers`. Directory matching is case-insensitive on Windows and `dotnet-cqrs` is first in
`detectionOrder`, so this repository profiles *itself* as ".NET CQRS" on the strength of
`commands/` and `hooks/runtime/handlers/` — and the same scan on Linux would not match.

Agents read that file as ground truth and take their build and test commands from it. Read
the `**Tech Stack**:` line and sanity-check it before acting on anything downstream of it.

## House style

Explain **why**, not just what: every non-obvious rule carries one or two sentences naming
the concrete failure it prevents. Write connected sentences, not fragments. Be honest about
limits — when a mechanism cannot do something, say so plainly rather than omitting it. No
marketing superlatives, and **never an invented metric**: this project deliberately deleted
a fabricated token-savings percentage inherited from its source material, and
`scripts/context-bill.py` exists so the honest version can be produced instead. If a number
is an estimate, label it.

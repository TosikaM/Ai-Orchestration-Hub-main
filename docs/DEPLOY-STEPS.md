# Deployment Runbook

**How to turn this repository into a Claude Code plugin, publish it centrally, and use it.**

Every command below was run on the build machine except where a step is explicitly marked
unverified. Where something could not be verified, it says so rather than implying it works.

---

## Phase 0 — Prerequisites and local verification

Do this before anything touches GitHub. If the repository does not validate locally it
will not validate for a colleague either, and debugging that over Slack is miserable.

```bash
node --version      # need >= 18   (verified here: v24.20.0)
python --version    # need >= 3.11 (verified here: 3.12.10)
python -m pip install pyyaml
```

On Windows, `python3` is the Microsoft Store stub and will fail. Use `python`.

```bash
python scripts/gen-content.py --check      # generated content is in sync
python scripts/validate-structure.py       # 23 checks, must exit 0
python scripts/redact.py --lint            # no catastrophic regex
python scripts/audit-agent-surface.py      # our own agent surface
```

`validate-structure.py` is the gate. If it does not print `ALL CHECKS PASSED`, stop —
publishing a plugin that fails its own validator wastes everybody's first impression.

---

## Phase 1 — Install locally and prove the gates fire

**Install from the local directory before publishing.** This is the step most people skip,
and the one that catches a broken manifest while the blast radius is still one machine.

```bash
npm install -g @anthropic-ai/claude-code    # the claude CLI is not currently on PATH
claude --version                            # must be >= 2.1
```

Then from inside this repository:

```
/plugin marketplace add ./
/plugin install orchestrator@algoworks
```

The trailing slash matters. A bare `.` is rejected with *"Invalid marketplace source
format"*; `./` is accepted. From a terminal the same thing is
`claude plugin marketplace add ./`.

### Prove it actually works

Two things must be true, and only one of them is visible:

```
/skills          # should list 16, including sdlc-orchestrator and knowledge-base
/analyze         # should dispatch, not "unknown command"
```

Then the part that matters more. **Ask Claude to edit any source file.** The fact-forcing
gate must deny the first edit with a message beginning `[Fact-Forcing Gate]`.

> **If the edit goes through without a denial, the hooks are not loading.** That is the
> single most important signal in this runbook, because everything else — skills, agents,
> commands — will look completely fine while none of the five blocking gates exists.
> See Troubleshooting.

You can test the gate logic directly without Claude, which separates "is the hook broken"
from "is the hook wired":

```bash
export ORCHESTRATOR_PLUGIN_ROOT="$PWD"
echo '{"session_id":"t","tool_name":"Edit","tool_input":{"file_path":"src/x.ts"}}' \
  | node hooks/runtime/run.js pre:edit-write:fact-force
```

A `permissionDecision: "deny"` means the runtime is fine and only the wiring is in question.

---

## Phase 2 — Publish to GitHub

This repository is **not currently a git repository**. That is step one.

```bash
git init
git add -A
git commit -m "AI Orchestrator Hub v3.1.0"
git branch -M main
git remote add origin https://github.com/abhishek-narula-algoworks/Ai-Orchestration-Hub.git
git push -u origin main
git tag v3.1.0 && git push --tags
```

The repository name must match `hub.config.json` -> `hub.repository`
(`abhishek-narula-algoworks/Ai-Orchestration-Hub`); the version check and the install ref both depend on it.

**Private is fine and is the intended shape** — the marketplace mechanism is public even
when the repository is not. See the risk note in Phase 3.

---

## Phase 3 — Install from the marketplace

```
/plugin marketplace add abhishek-narula-algoworks/Ai-Orchestration-Hub
/plugin install orchestrator@algoworks
```

> **The one operational unknown.** Whether `/plugin marketplace add` against a *private*
> repository needs credentials the public path does not has **not been verified here** —
> no `claude` CLI was available on the build machine. Test it with a throwaway private
> repo before committing the whole organization to this path.
>
> If it does not work, `scripts/install-team.ps1` is the fallback: it links the content
> into `~/.claude/` directly with an ownership marker so it can be cleanly removed. It is
> deliberately the secondary path, because hand-rolled installation means owning symlink
> semantics, orphan pruning and upgrade migrations yourself.

---

## Phase 4 — Central rollout to the whole organization

Three layers. Use all three; each covers a different failure.

### 4a. Managed policy — the floor nobody can skip

Push this by MDM, Intune or Group Policy. It applies to every machine and cannot be
overridden by a user's own settings:

| OS | Path |
|---|---|
| Windows | `C:\ProgramData\ClaudeCode\managed-settings.json` |
| macOS | `/Library/Application Support/ClaudeCode/managed-settings.json` |
| Linux / WSL | `/etc/claude-code/managed-settings.json` |

```json
{
  "extraKnownMarketplaces": {
    "algoworks": {
      "source": { "source": "github", "repo": "abhishek-narula-algoworks/Ai-Orchestration-Hub" }
    }
  },
  "enabledPlugins": { "orchestrator@algoworks": true }
}
```

This is what makes the answer to *"does everyone have it?"* be **yes by construction**
rather than *"we sent an email."*

### 4b. Per-repository settings — arrives with the code

Commit `.claude/settings.json` into each repository. A new joiner clones and has the
orchestrator without being told it exists:

```json
{
  "extraKnownMarketplaces": {
    "algoworks": {
      "source": { "source": "github", "repo": "abhishek-narula-algoworks/Ai-Orchestration-Hub" }
    }
  },
  "enabledPlugins": { "orchestrator@algoworks": true },
  "env": { "ORCHESTRATOR_HOOK_PROFILE": "standard" }
}
```

### 4c. Per-repository policy — narrowing only

Optional, in `.github/orchestrator-policy.json`:

```json
{
  "repository": {
    "autonomy": { "level": 2 },
    "qualityGate": { "aiAssessment": { "minimumScore": 90 } }
  }
}
```

A repository may only **restrict** what its organization allows. `scripts/policy.py`
refuses a widening and reports it — which matters because policy lives in files an agent
can edit, and an agent optimizing for "make the task complete" finds `autonomy.level`
eventually.

### Verify a rollout

```bash
python scripts/policy.py resolve       # what this repo may actually do
python scripts/policy.py autonomy      # the level, and what each level means
python scripts/orchestrator.py doctor  # install integrity, drift, pending upgrades
```

---

## Phase 5 — Connect a repository

Once per repository, and it is genuinely two commands:

```
/orchestrator-init
```

then

```bash
python scripts/orchestrator.py doctor
```

**Only two files land in a consumer repository:**

| Path | Why |
|---|---|
| `.github/orchestrator-context.md` | the repo's own profile — stack, layers, conventions |
| `.github/orchestrator-install.json` | install state; what makes `doctor`, `repair` and `uninstall` possible |

Everything else — 16 skills, 10 agents, 26 commands, 16 hooks — stays in the plugin. That
is why an upgrade is one command instead of a pull request per repository, and why a sync
can no longer overwrite a team's own files.

---

## Phase 6 — Daily use

```
/sdlc-start  add an ImpactInvestment field to the donation form
```

runs the full pipeline: analyze -> implement -> (review parallel test) -> deploy ->
complete, stopping at four human gates. Or drive it a step at a time:

| Command | Does |
|---|---|
| `/analyze <what>` | trace a field through every layer, each cited `file:line` |
| `/implement <what>` | write the change, following the repo's conventions |
| `/review` `/test` `/qa` | score 0-100, generate tests, generate E2E specs |
| `/verify` | six-phase pre-PR gate; "not run" is never reported as "passed" |
| `/security` | eight passes, including an audit of our own agent surface |
| `/adr <question>` | frame options, record the decision |
| `/repo` | switch repos, manage the cross-repo band |
| `/knowledge` | query ingested client documentation, with citations |
| `/budget` | the context bill, and a ranked list of what to cut |
| `/doctor` | diagnose the install |

### Answering a human gate

The pipeline writes an artifact and stops. A `Stop` hook blocks the session until a
verdict file exists — **the agent cannot clear its own gate.**

```bash
python scripts/pipeline.py status
python scripts/pipeline.py approve <pipelineId> <phase>
python scripts/pipeline.py request-changes <pipelineId> <phase> --note "..."
```

Because a verdict is just a JSON file, anything that can write it can clear a gate: the
CLI, the view-plane panel, or Claude Desktop with a filesystem connector. That was
deliberate — the panel is a nicety over a file protocol, never a dependency.

### Memory

Learnings are captured as **candidates**. Meeting the criteria (confidence >= 0.7 and seen
in >= 2 repos) proposes an entry; it does not promote one:

```bash
python scripts/memory.py pending
python scripts/memory.py approve <id> --by "<name>"
python scripts/memory.py reject  <id> --reason "..."
```

Shared memory syncs to every connected repository, so a wrong entry is wrong everywhere.
The criteria measure how *often* something was observed, never whether it is *true*.

---

## Phase 7 — Releasing an update

```bash
python scripts/release.py --bump minor     # bumps 3 files, then validates
git add -A && git commit -m "release: 3.2.0"
git tag v3.2.0 && git push origin main --tags
```

If the validator fails, the bump is **reverted** rather than left half-applied.

Consumers pick it up with `/plugin marketplace update algoworks`. That is a manual
command — nothing auto-updates today, which is the honest state. `orchestrator.py doctor`
reports a pending upgrade by comparing the installed `hubVersion` against the current hub,
so a stale install is at least visible.

If a release changes on-disk state in a consumer repository, add a migration under
`migrations/` and it runs via `python scripts/orchestrator.py upgrade`.

---

## Troubleshooting

### The hooks are not firing — read this first

This is the failure that looks like success. Skills load, commands dispatch, and no gate
ever denies anything.

**The hooks manifest is at `hooks/hooks.json`, and this is now CONFIRMED.** Installed
against claude 2.1.266, `claude plugin details orchestrator@algoworks` reports
`Hooks (5)  PreToolUse, SessionStart, PreCompact, Stop, SessionEnd`. The path is correct.

If a first edit is nonetheless never denied:

1. Confirm the runtime works standalone (the Phase 1 `node hooks/runtime/run.js` command).
   A `deny` there means the logic is fine and only the wiring is wrong.
2. Try moving the file to `.claude-plugin/hooks.json` and reinstalling. One of the two is
   the convention path.
3. Update the path in `scripts/validate-structure.py`, `scripts/audit-agent-surface.py`
   and `hooks/runtime/registry.json` to match whichever works, and record which one it was.

Never declare `hooks` in `plugin.json` — it produces `Duplicate hooks file detected`.
`check_no_hooks_in_plugin_manifest` fails the build if it reappears.

### `agents: Invalid input` on install

`plugin.json` must not carry an `agents` key; the validator rejects it and the error does
not name the cause. Agents under `agents/` are auto-discovered.
`check_plugin_manifest_component_keys` guards this.

### A gate is too aggressive

```bash
export ORCHESTRATOR_GATE_EXEMPT_GLOBS="docs/**,*.generated.ts"   # narrow
export ORCHESTRATOR_HOOK_PROFILE=minimal                         # fewer gates
export ORCHESTRATOR_HOOKS_ENABLED=false                          # all off
```

Prefer the narrowest. A gate that only offers "turn it all off" gets turned all off
permanently the first time it is inconvenient. Note that `prompt-defense`, the memory
redaction guard and the autonomy gate ignore the profile — those are security controls,
not friction dials.

### `python3` fails on Windows

That is the Microsoft Store stub. Use `python`.

### Everything reports fine but nothing is enforced

```bash
python scripts/orchestrator.py doctor
```

Several readers fall back to built-in defaults when their config is unreadable and log it
where nobody looks. A repository whose `config/` failed to sync runs on defaults silently,
forever. `doctor` is the only thing that will tell you.

---

## Known limits, stated plainly

| Limit | Detail |
|---|---|
| ~~Hooks path unverified~~ | **RESOLVED.** `claude plugin details` reports Hooks (5) from `hooks/hooks.json`. |
| **Private marketplace auth unverified** | Local install is verified; a *private GitHub* source is not. Test with a throwaway private repo before rolling out. |
| **No auto-update** | `/plugin marketplace update` is manual; `doctor` reports staleness. |
| ~~Git/PR not orchestrated~~ | **RESOLVED.** `scripts/git-flow.py` and the `git-workflow` skill. Merge remains manual at every autonomy level, deliberately. |
| **12 commands have no eval coverage** | `orchestrator-init, plan, pipeline, qa, verify, release, document, loop, mcp-compose, git, mode, doctor`. Changing them has no defined blast radius in the suite. |
| **Cost reporting unconfigured** | `config/model-pricing.json` ships with null prices on purpose. Fill it from the official pricing page; until then only token counts are reported. |
| **Claude Desktop is not a target** | No plugins, no `PreToolUse` deny. Desktop works for reading artifacts and approving gates, not for running the pipeline. |
| **Source leaves the environment** | `policy.json` -> `dataPolicy` says so explicitly. Do not sell this into an air-gapped account without solving it first. |

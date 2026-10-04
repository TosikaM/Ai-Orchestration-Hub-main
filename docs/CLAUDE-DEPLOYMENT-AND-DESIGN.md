# Deploying and Designing the Orchestrator on Claude

**Version:** 3.1 · **Audience:** the engineer who has to stand this up, and the reviewer who has to sign it off
**Answers:** the twenty findings in `OrchestratorReview.md`
**Companion:** `ARCHITECTURE-AND-SETUP.md` (how it works) · this file (how it ships, and why it is shaped this way)

---

## 0. The one-paragraph version

The review's central criticism was correct and is now structurally resolved: the previous
design named "LLM assistance" and never defined the runtime, so grounding could only ever
be advisory. **Claude Code *is* the runtime now.** The orchestrator ships as a Claude Code
plugin from a private GitHub repository; a team installs it with two commands or one
committed settings file. What that buys is not convenience — it is the ability to *block*.
A `PreToolUse` hook returns `permissionDecision: "deny"` and the action does not happen.
The system no longer polices prose it cannot control; it polices the action stream, which
is where a hallucination stops being a sentence and becomes an edit. Everything else in
this document follows from that one move.

---

## 1. What the review asked for, and where it stands

The review was written against v3.0.0. This is the honest status of all twenty points
against what is now on disk. "Closed" means there is code and a test or gate behind it,
not a paragraph.

| # | Finding | Status | Where |
|---|---|---|---|
| 1 | Good foundation, keep the architecture | Kept | three planes, unchanged in shape |
| 2 | **Claude not defined / no LLM gateway** | **Closed** | Claude Code is the runtime; `scripts/llm.py` is the *headless* gateway |
| 3 | MCP needs to be a production layer | **Closed** | `config/tool-registry.json` → `governance`: owner, environment, riskClass, allowedOperations, auditLog, authentication — enforced by `audit-agent-surface.py` |
| 4 | Human approval gates as first-class | **Closed** | `human-gate.js` blocks `Stop`; 4 named gates in `policy.json` |
| 5 | Quality gate = deterministic + AI | **Closed** | `policy.json → qualityGate` is a conjunction; a check that could not run counts as failed |
| 6 | Explicit security layer | **Closed** | redaction taxonomy, egress ledger, prompt-defense, config-protection, destructive-gate, agent-surface audit, per-agent permission model |
| 7 | Prompt lifecycle management | **Closed** | `version`, `owner`, `lastReviewed`, `evalIds` on all 26 commands; `check_prompt_lifecycle` validates semver and that every `evalIds` entry exists |
| 8 | AI evaluation framework | **Closed** | 18 evals, 2 tiers, diff-selected, strict-output runner, gates PRs |
| 9 | Observability / telemetry | **Closed** | hash-chained local ledgers + `scripts/telemetry.py rollup` — engineering, AI and financial views |
| 10 | Memory governance | **Closed** | candidate → pending-approval → approved / rejected → retired, human-gated |
| 11 | Context engine | **Partial** | context file + structural graph + budget ladder; retrieval pipeline is P1 |
| 12 | Graph beyond regex | **Open, acknowledged** | `graph.py` says so in its own docstring — P2 |
| 13 | Cross-repo contract enforcement | **Partial, acknowledged** | band carries contracts; it does not verify consumption, and says so |
| 14 | Autonomy levels | **Closed** | levels 0–5, `autonomy-gate.js`, default ceiling 3 |
| 15 | Git/PR first-class | **Open** | P0 — see §9 |
| 16 | Enterprise configuration model | **Closed** | `config/policy.json` with a narrowing rule |
| 17 | Do not treat file counts as maturity | Adopted | no maturity claims anywhere in the docs |
| 18 | Add the platform layers | See §3 | |
| 19 | P0/P1/P2 priority | See §9 | |
| 20 | Position as a platform, not a framework | Adopted | see §10 |

**Fourteen closed, three partial with their limits stated in code, one open, one
context.** The open item is §15 (Git/PR orchestration), priced in §9. Nothing here is
claimed as done that is not — every row was re-verified against the files on 2026-09-09,
with the toolchain installed and the validator passing 22/22.

### 1.1 Four defects the review did not find, that we did

Reading ECC and gstack against this build surfaced bugs in *our* code. They are listed
here rather than quietly fixed, because three of the four are the same failure mode this
whole system exists to prevent — a control that looks installed and is not.

| Defect | Consequence | Status |
|---|---|---|
| `stdin.js` read unbounded and resolved on a 2s timer | A large or slow payload → partial JSON → empty context → **all five blocking gates silently allowed**. Nothing logged. | **Fixed** — 1 MiB cap, truncation propagated, blocking hooks fail closed |
| `run.js` / `dispatch.js` exited before stdout drained | A denial longer than the pipe buffer is truncated; the harness cannot parse a decision out of it and proceeds as if permitted. Long denials are the useful ones. | **Fixed** — write-with-callback plus a watchdog |
| `policy.json` declared `trackedBy: scripts/telemetry.py` | The script did not exist. A cost ceiling enforced by nothing, in the file that governs every other gate. | **Fixed** — the script now exists |
| MEDIUM redaction findings on unattended writes | "Confirm with the user" degrades to "proceed" when there is no user. `memory.py capture` runs from hooks and CI, and writes to a store that syncs org-wide. | **Fixed** — MEDIUM blocks when non-interactive; `--allow-medium` for the deliberate case |

The first one is worth dwelling on. Five blocking gates, a hook runtime, a policy engine
and a CI suite — and a slow pipe turned all of it off without a log line. Defence in
depth is worth exactly as much as its weakest shared dependency, and every gate shared
this one.

---

## 2. Why a plugin, and why that answers finding #2

The review said: *"searching the blueprint for 'Claude' returns no occurrence."* That was
damning and correct. The fix is not to add a chapter about Claude — it is to make Claude
Code the execution substrate, and delete the parts of the old design that existed only
because there wasn't one.

### What got deleted

Five of the twelve services in v3.0.0 were re-implementations of platform primitives:

| Old service | What it did | What replaced it |
|---|---|---|
| `skillLoader` | four-tier `SKILL.md` resolution, frontmatter parsing, command→skill mapping | **native skill discovery** — a skill *is* the command |
| `chatParticipant` | ~400 lines registering `@orchestrator`, routing 21 commands, assembling prompts | **native dispatch** |
| `hubSync` | four-strategy content distribution | `/plugin marketplace update` |
| `tokenBudget` (trim) | trimming sections before streaming | the platform manages context; measurement stays, trimming goes |
| `grounding` (advisory) | post-hoc evidence manifest | survives, and gains a **blocking** counterpart it could never have had |

Roughly 3,000 lines of TypeScript removed. That is not a loss of capability. It is the
removal of a shim that existed to imitate a runtime.

### What that unlocks — the thing the old architecture could not do

The v3.0.0 document was honest about its own ceiling:

> The extension **does not own the generation stream** … Grounding is enforced at
> Pre-flight (Strong), In-prompt (Moderate), Post-hoc (**Advisory — cannot block**).

Every word true, and entirely a consequence of the deployment choice. You do not need to
own the *generation* stream to own the *action* stream:

```json
{ "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "<text the model reads and must respond to>" } }
```

The enforcement table gains a row that changes the system's character:

| Stage | Mechanism | Strength |
|---|---|---|
| Pre-flight | verify files/symbols against the structural graph | Strong |
| **Pre-action** | **deny the first Edit/Write per file until retrieved facts are presented** | **Blocking** |
| In-prompt | the Four Laws, the grounding contract, truncation markers | Moderate |
| Post-hoc | audit for uncited claims | Advisory |

And the honest amendment: what the system now prevents is **an edit to a file whose blast
radius the agent never established.** That is a stronger and more defensible claim than
either "we prevent hallucination" (false) or "we can only advise" (weak).

---

## 3. The architecture the review asked for, mapped to what exists

The review sketched a target architecture. Here it is against real paths:

```
            Developer / BA / QA
                    │
      Claude Code (terminal · VS Code · JetBrains)
                    │
        ┌───────────┴────────────┐
        │   ORCHESTRATOR PLUGIN  │   .claude-plugin/{plugin,marketplace,hooks}.json
        └───────────┬────────────┘
                    │
   ┌────────────────┼─────────────────┬──────────────────┐
   │                │                 │                  │
Context Engine   Agent Runtime    Policy Engine     Hook Runtime
context-gen.py   agents/ (10)     policy.json       hooks/runtime/ (16)
graph.py         skills/ (16)     policy.py         ├ fact-force      BLOCKING
grounding.py     commands/ (26)   autonomy 0-5      ├ autonomy-gate   BLOCKING
context-bill.py  contexts/ (3)    permissions       ├ config-protect  BLOCKING
                                  dataPolicy        ├ destructive     BLOCKING
                                  qualityGate       ├ human-gate      BLOCKING
                                  costLimits        └ 11 more
        │                                                  │
        └──────────────────┬───────────────────────────────┘
                           │
                  ┌────────┴────────┐
                  │  LLM ACCESS     │
                  │  interactive →  Claude Code owns it
                  │  headless    →  scripts/llm.py
                  └────────┬────────┘
                           │
                  ┌────────┴────────┐
                  │  TOOL / MCP     │  tool-registry.json + governance
                  └────────┬────────┘
                           │
        Git · Tracker · CI · Scanners · Docs
                           │
                  ┌────────┴────────┐
                  │ OBSERVABILITY   │  telemetry.jsonl · egress.jsonl · llm.jsonl
                  └────────┬────────┘
                           │
                  ┌────────┴────────┐
                  │ MEMORY + EVALS  │  4 tiers, human-gated promotion · 18 evals
                  └─────────────────┘
                           │
                  ┌────────┴────────┐
                  │   VIEW PLANE    │  view/ — reads state, writes one verdict file
                  └─────────────────┘
```

**The one deliberate deviation from the review's sketch:** the review put an LLM Gateway
in the main path, between the agent runtime and Claude. This design does not, for the
interactive path. Putting a proxy in front of Claude Code would mean re-implementing
auth, retries, streaming and context management in order to sit in front of a runtime
that already does all four — the exact mistake that produced `chatParticipant.ts`. The
gateway exists where it is genuinely needed: unattended calls, where nothing else is
handling model choice, retries, cost or egress.

---

## 4. Using Claude Code's feature surface deliberately

This is the "strong design approach" question. Each feature, what it is used for, and
what would have had to be hand-built without it.

| Claude Code feature | Used for | Replaces |
|---|---|---|
| **Skills** (`skills/*/SKILL.md`) | the 16 SDLC protocols; progressive disclosure via `references/` | `skillLoader.ts`, four-tier resolution |
| **Frontmatter `allowed-tools`** | least privilege per skill; `grounding-guard` and `structural-graph` cannot write, enforced by CI | nothing — this did not exist before |
| **Subagents** (`agents/*.agent.md`) | the 10 SDLC roles, each with its own context window and tool surface | a hand-rolled agent dispatcher |
| **Slash commands** (`commands/*.md`) | 26 entry points; `argument-hint` gives inline help | the 21-command `switch` in a chat participant |
| **`PreToolUse` hooks** | 5 blocking gates: fact-force, autonomy, config-protection, destructive, MCP health | **nothing. This capability did not exist.** |
| **`Stop` hooks** | human gate (blocking), citation guard, learning capture, staleness, telemetry | a toast notification |
| **`SessionStart` hook** | the small always-on set: pending gates, active decisions, staleness, budget | guaranteed context injection via a chat participant |
| **`PreCompact` hook** | checkpoint the in-flight pipeline before the window is rewritten | **nothing — this was a real defect.** A long phase lost its state on compaction |
| **`SessionEnd` hook** | release cross-repo band locks, flush telemetry | a stuck lock that looks like a hang |
| **Plugin marketplace** | distribution and one-command upgrade | `hubSync.ts`, four sync strategies, ~200 lines of installer rules |
| **`userConfig`** | five user-flippable options in the plugin UI | thirteen VS Code settings, nine of which silently did nothing |
| **Project-scoped `.claude/skills/`** | per-repo skill overrides | a bespoke "skill packs" tier |
| **`CLAUDE_PLUGIN_ROOT`** | path resolution in hook commands | an inlined fallback resolver in every hook entry |
| **Headless `claude -p`** | the eval runner and the LLM gateway | a provider matrix and credential handling that blocked the eval runner for a whole version |

Two features used **deliberately sparingly**:

- **MCP servers: zero enabled by default.** Every MCP tool description is always-on
  context competing with the discovery budget. The registry declares what an org *may*
  enable; a developer turns one on knowingly. Ceiling: ≤1 connector, ≤30 tools.
- **The model is not overridden interactively.** The plugin does not force a model on a
  developer's session. Silently swapping somebody's model mid-conversation is a
  surprising thing to do, and the cost lever that matters lives on the headless path.

---

## 5. Centralizing it for the team

This is the deliverable the review's §16 and your own question both point at: one place
to configure, everybody gets the same thing.

### 5.1 The recommended path — a committed settings file

Two commands work, but they are a thing each person must remember to run. A settings
file is reviewable, diffable, and arrives with the repository.

Put this in `~/.claude/settings.json` (per person) or check it into a repo as
`.claude/settings.json` (per project — this is the one to prefer for a team):

```jsonc
{
  "extraKnownMarketplaces": {
    "algoworks": {
      "source": { "source": "github", "repo": "abhishek-narula-algoworks/Ai-Orchestration-Hub" }
    }
  },
  "enabledPlugins": {
    "orchestrator@algoworks": true
  }
}
```

That is the whole team rollout. A new engineer clones a repo that has it, opens Claude
Code, and has the 16 skills, 10 agents, 26 commands and 16 hooks — at the same versions
as everybody else, because the marketplace pins one.

### 5.2 The interactive path

```
/plugin marketplace add abhishek-narula-algoworks/Ai-Orchestration-Hub
/plugin install orchestrator@algoworks
```

Then, once per repository:

```
/orchestrator-init                              # generates .github/orchestrator-context.md
python scripts/orchestrator.py doctor           # confirms the install
```

### 5.3 What actually lands in a consumer repository

**Two files.** That is the single biggest simplification against v3.0.0, which copied
fourteen paths into every repo:

| Path | Why it is repo-local |
|---|---|
| `.github/orchestrator-context.md` | genuinely per-repo; the densest artifact in the system |
| `.github/orchestrator-install.json` | install state — what enables `doctor`, `repair` and `uninstall` |

Agents, skills, prompts, contexts, hooks and shared memory **stop being copied**. They
live in the plugin. The consequences are worth stating because they are the practical
argument for this whole model:

- The managed `.gitignore` block drops from ten paths to two.
- An upgrade is `/plugin marketplace update algoworks`, not N pull requests.
- The data-loss class where a sync overwrites a team's own `copilot-instructions.md`
  **cannot recur**, because nothing writes to `.github/instructions/` any more.

### 5.4 Per-repository policy, without forking the platform

A repository may narrow what its organization allows, in
`.github/orchestrator-policy.json`:

```json
{
  "repository": {
    "autonomy": { "level": 2 },
    "qualityGate": { "aiAssessment": { "minimumScore": 90 } }
  }
}
```

**It may only narrow.** `scripts/policy.py` refuses a widening from a narrower layer and
reports the attempt. This matters because policy lives in files an agent can edit, and an
agent optimizing for "make the task complete" will find `autonomy.level` eventually. The
narrowing rule is what makes finding it useless.

### 5.5 Verifying a rollout

```
python scripts/policy.py resolve       # what this repo is actually permitted to do
python scripts/policy.py autonomy      # the level and what it means
python scripts/policy.py gates         # the composite quality gate and the 4 approvals
python scripts/orchestrator.py doctor  # install integrity, drift, pending upgrades
python scripts/audit-agent-surface.py  # our own agent surface, including MCP governance
```

`doctor` earns its place on one check in particular: several readers fall back to
built-in defaults when their config is unreadable, and log it where nobody looks. A repo
whose `config/` failed to sync is running on defaults, silently, forever. `doctor` is the
only thing that would ever say so.

---

## 6. Claude Desktop vs Claude Code — the honest answer

You asked whether this can be centralized in Claude Desktop *or* Claude Code. They are
not equivalent targets and it is worth being direct about why.

| | Claude Code | Claude Desktop |
|---|---|---|
| Plugins (skills/agents/commands/hooks) | **Yes** — the whole distribution model | No |
| `PreToolUse` deny — the blocking gates | **Yes** | No |
| Repository filesystem access | **Yes** | Only via MCP |
| Runs the SDLC pipeline | **Yes** | No |
| MCP connectors | Yes | Yes |

**The orchestrator targets Claude Code. It is not a Claude Desktop product**, and
pretending otherwise would mean shipping something whose central guarantee — that a gate
can block — is absent on half its claimed surface.

What Desktop *is* good for, and the supported story:

- **Reading the artifacts.** Gate review documents, ADRs, context files and pipeline
  checkpoints are all plain Markdown and JSON on disk. A filesystem MCP server pointed at
  the repository gives a product owner or a tech lead a way to read and approve without
  installing a development environment.
- **The approval side of a human gate.** A verdict is a JSON file. Anything that can
  write that file can clear a gate — Desktop with a filesystem connector, the CLI, or the
  view plane's panel. That was a deliberate design choice: the panel is a nicety over a
  file protocol, never a dependency.

So: **engineers use Claude Code; reviewers and approvers can live in Desktop.** Do not
promise Desktop users the pipeline.

---

## 7. Running against a local or self-hosted model

You asked for a local-import option. Here is what is genuinely available, separated from
what would be marketing.

**What works today.** The headless path (`scripts/llm.py`) shells out to a CLI and parses
its output. `config/policy.json → model` selects the model and
`config/model-pricing.json` accounts for it. Pointing that at a different endpoint is a
contained change: one `call_model` function.

**What does not work, and why saying so matters.** The *interactive* path is Claude Code,
and Claude Code is the thing providing skills, subagents and — critically — the
`PreToolUse` deny. A local model reached through a different client does not give you the
hook runtime, which means it does not give you any of the five blocking gates. You would
keep the content plane and lose the enforcement, which is most of the value.

**Therefore, the supported shapes:**

| Requirement | Shape |
|---|---|
| Source may not leave the environment | **Not supported in v3.1.** `policy.json → dataPolicy.sourceCodeMayLeaveEnvironment` is `true` and says so plainly rather than implying local inference. Do not sell this into an air-gapped account without solving it first. |
| Cost control / cheaper tier for bulk work | **Supported.** Route mechanical skills to the fast tier in `policy.json → model.routing`. This is the largest cost lever in the system. |
| A local model for evals or batch jobs | **Supported with a change** to `call_model`, keeping the content plane and the CI gates. |
| A local model for interactive development | **Not supported.** You would lose the hooks, and the hooks are the enforcement. |

The `dataPolicy` block exists precisely so this conversation happens against a written
answer instead of an optimistic one.

---

## 8. The complete SDLC, end to end

What a developer actually does, and what the system does around them.

```
Requirement (ticket, doc, conversation)
   │
   ├─ /knowledge search "<the requirement>"        cite the spec, do not recall it
   │
/sdlc-start "<the requirement>"
   │
   ├─ PHASE analyze        agent: analyst      skill: repo-context-builder
   │    5 mandatory steps; every layer cited file:line
   │    ▶ GATE 1 requirement   owner: product/BA   "Is this what was asked for?"
   │    ▶ GATE 2 design        owner: tech lead    "Is this the right change?"
   │      Stop hook BLOCKS. The agent cannot clear its own gate.
   │
   ├─ PHASE implement      agent: developer    skill: cqrs-developer
   │    fact-force denies the first edit per file until importers + affected
   │    exports + the user's verbatim instruction are presented
   │    autonomy-gate denies anything above the repo's level
   │
   ├─ PHASE review ∥ test  agents: reviewer, qa   (genuinely parallel — DAG siblings)
   │    deterministic checks MUST pass · AI score ≥ 80 · human review
   │    a check that could not run counts as FAILED
   │    ▶ GATE 3 code       owner: developer   "Would you merge this?"
   │
   ├─ PHASE deploy         skill: release-engineering
   │    readiness is BLOCKED, not warned, on: red CI · unreviewed migration ·
   │    open advisory · unrun verification phase · open HIGH finding
   │    ▶ GATE 4 production owner: release owner  "Willing to be paged for this?"
   │
   └─ PHASE complete       skill: continuous-learning
        learning captured as a CANDIDATE — never written to shared memory directly

Throughout: PreCompact checkpoints the pipeline · Stop captures learnings async ·
SessionEnd releases band locks · every memory and context write is redaction-scanned
```

### Cross-repo, maintained and unchanged

The band protocol survives intact, because it was one of the genuinely good ideas:

```
shared-library → command-api → query-api → frontend
   (contract)     (writes it)   (reads it)   (shows it)
```

Dependency-first, producers before consumers. Upstream contracts must be consumed
downstream **as named** — renaming one locally because it reads better is how a band
produces four repositories that each compile and do not talk to each other.

**Its honest limit, stated in the skill itself:** the band tracks contracts and order. It
does not verify that a downstream repo wired the contract to the *right thing*. That
needs an integration test crossing repositories, which this system does not run. Finding
#13 asked for contract enforcement; this is the part that is still missing, and §9 prices
it.

### Memory, maintained and now governed

Four tiers — shared, per-repo, decisions, session — unchanged in shape. What changed is
the gate in front of the shared one, which is what finding #10 asked for:

```
candidate ──criteria met──> pending-approval ──human──> approved ──> retired
                                             └─human──> rejected (durable)
```

Criteria (confidence ≥ 0.7 **and** seen in ≥ 2 repos) make something a *candidate*.
They measure how often it was observed, not whether it is true, and no arithmetic over
observation counts ever will. Rejection is durable so candidates do not re-propose
forever and train the reviewer to stop reading.

---

## 9. What is still missing, and what it costs

Named honestly, with effort, because "we have 16 skills" is not the same claim as "this
is production-ready".

### P0 — before a customer engagement

| Item | Why it blocks | Effort |
|---|---|---|
| **Git/PR orchestration** (#15) | The lifecycle currently ends at a working tree. Branch → commit → PR → CI → merge is the developer-visible product, and right now a human does all of it. Needs a `git-workflow` skill plus `scripts/git-flow.py`, gated at autonomy 4. | M |
| **Fill the price table** | `config/model-pricing.json` ships with nulls on purpose. Until it is filled there is no cost reporting — only token counts. | XS |
| **Eval coverage for 11 commands** | `check_prompt_lifecycle` reports `orchestrator-init, plan, pipeline, qa, verify, release, document, loop, mcp-compose, mode, doctor` as having no eval case. Honest, and a gap: a change to those has no defined blast radius in the suite. | M |
| **Verify private-repo marketplace auth** | The one operational unknown in the whole distribution model. Test with a throwaway private repo before committing an org to it. Fallback exists: `scripts/install-team.ps1`. | XS |

### P1 — soon after a pilot

| Item | Note | Effort |
|---|---|---|
| Structured headless output | `eval-runner.py` passes the prompt on **argv** and regexes a score out of free text, so it captures no tokens, no cost and no session id — and inherits argv length and quoting risk on Windows, our primary platform. Move to `--output-format json` and stdin. | S |
| Context retrieval engine (#11) | Today: context file + graph + budget ladder. Wanted: requirement → modules → dependencies → tests → rules | L |
| Cross-repo contract tests (#13) | Generate a contract test at the producer, run it at each consumer | M |
| Golden eval set (#8) | 18 cases test behaviour; a set of real stories would measure acceptance rate | M |

### P2 — scale

AST/LSP structural graph (#12) · multi-model support · predictive estimation ·
automated prompt optimization.

---

## 10. Positioning

The review's final point is right and worth adopting verbatim in spirit: this is not a
"Claude Development Framework". The defensible layer is not the model.

> **An AI-native software engineering platform, with Claude as the reasoning engine.**

What makes it defensible is everything that is *not* the model: the context engine, the
orchestration DAG, the agents and skills, the governed tool layer, the composite quality
gate, the policy engine, the governed memory, and the telemetry. Those turn Claude from
*an AI coding assistant* into *an AI engineering workforce operating under an engineering
control system.*

The one honest caveat to that framing: the platform currently depends on Claude Code
specifically — not on Claude the model — because the enforcement lives in its hook
runtime. That is a real coupling and it is the price of being able to block. It is the
right trade at this stage, and it should be stated rather than hidden behind
"model-agnostic".

---

## 11. Risks

| # | Risk | Assessment | Mitigation |
|---|---|---|---|
| R1 | Private-repo marketplace auth may need credentials the public path does not | The one operational unknown that could change the layout | Test in week 1; `install-team.ps1` is the fallback |
| R2 | Claude Code ≥ 2.1 required | Low — current line | `doctor` checks it; stated in README |
| R3 | Fact-forcing gate friction | Real. Week one feels like fighting the tool | Ships at `standard`; `ORCHESTRATOR_GATE_EXEMPT_GLOBS`; the structural graph makes compliance one CLI call |
| R4 | Autonomy ceiling frustrates a team that wants level 4 | Likely, and healthy | Raising it is one policy edit plus a recorded decision |
| R5 | Two planes drift | Why the extension was nearly retired | View plane reads files and writes **one** verdict file; CI enforces it |
| R6 | Neither Node nor Python installed on a dev machine | Observed on this build machine | `winget install OpenJS.NodeJS.LTS Python.Python.3.12`; `doctor` reports it |
| R7 | Memory approval becomes a rubber stamp | The realistic failure of any gate | The request artifact states blast radius and asks "would you write this on the team wiki?" |

---

## Appendix A — Provenance: what we took from ECC and gstack, and what we refused

Both repositories were read directly (`C:\Users\AbhishekNarula\Source Code\ECC` and
`…\gstack`) across nine dimensions: plugin manifest, agent and skill authoring, hook
runtime, install lifecycle, LLM and MCP access, Claude integration, skill generation,
budgets and evals, and memory governance. 117 mechanisms were assessed — 57 adopt,
53 adapt, 7 reject.

### A.1 Two findings that were about to break the install

These justify the whole exercise, because neither is discoverable from documentation and
both fail in ways that do not name their cause.

**The `agents` key.** Our `plugin.json` declared `"agents": ["./agents/"]`. ECC's
`.claude-plugin/PLUGIN_SCHEMA_NOTES.md:75-89` records that the Claude Code plugin
validator **rejects any `agents` field** — string, array of paths, or array of
directories — with the error `agents: Invalid input`. They removed it in #1459 and pinned
it with a test asserting the key is absent. Agent files under `agents/` are
auto-discovered by convention. **Removed, and now gated** by
`check_plugin_manifest_component_keys`.

**The hooks manifest path.** We placed ours at `.claude-plugin/hooks.json`, following our
own earlier design note. ECC places theirs at `hooks/hooks.json`, and the CLI error they
quote verbatim reads: *"The standard **hooks/hooks.json** is loaded automatically, so
manifest.hooks should only reference additional hook files."* That sentence names the
convention path, and it is not the one we used. If ECC is right, **none of our 16 hooks
ever fired, with no error anywhere** — every gate absent and every gate's documentation
intact. **Moved to `hooks/hooks.json`.**

> **Verify this one before trusting it.** Neither Node nor Python nor the `claude` CLI is
> installed on this build machine, so this was decided on ECC's evidence rather than by
> observation. The check is one command against an installed plugin:
> trigger any `Edit`, and confirm the fact-forcing gate denies. If it does not,
> the path is still wrong and this is the first place to look.

ECC's schema notes also carry a four-commit flip-flop table — the `hooks` key added and
removed twice in response to alternating bug reports (`22ad036` → `a7bc5f2` #52 →
`779085e` #88 → `e3a1306` #103). That format is worth copying: record the commit and the
issue that caused each reversal, so the next person does not re-derive it.

### A.2 Adopted

| From | Mechanism | Where it landed |
|---|---|---|
| ECC | Stdin cap where truncation is a **fail-closed security signal** | `stdin.js` + both runners — see ADR-0003; this fixed a live bug in our build |
| ECC | **Drain-before-exit** stdout writer | `run.js` / `dispatch.js` `finish()` |
| ECC | Manifest declares directories, not file lists | already ours; confirmed and kept |
| ECC | `"mcpServers": {}` as a deliberate opt-out, and a short plugin slug to keep generated MCP tool names under 64 chars | `plugin.json` + `_mcpServersNote` |
| ECC | Hook consent as an explicit, named, recorded decision | the decision-log requirement on autonomy grants |
| ECC | Doctor as a coded issue taxonomy with severity-derived exit code | `orchestrator.py doctor` |
| ECC | Confidence ladder on instincts, and a TTL on pending ones | `memory.py`; pending TTL is P1 |
| gstack | The budget ratchet with provenance and mutation pins | `token-budgets.json → derivation`, `measure-discovery-budget.py` |
| gstack | `allowed-tools` least privilege, CI-enforced | `check_allowed_tools`; read-only verifiers cannot hold `Write` |
| gstack | Two-tier, diff-selected evals with a **strict-output contract** | `evals/` — a verdictless case is FAILED, never skipped |
| gstack | Ownership proof model (strong / weak / foreign) with backup-before-overwrite | `connect-repo.ps1`, `orchestrator.py uninstall` |
| gstack | The merge-conflict rule for generated files, stated as an absolute | `CLAUDE.md`, `CONTRIBUTING.md` |
| gstack | Redaction tiers with the "a gate that cries wolf gets ignored" calibration | `config/redaction-patterns.json` |
| gstack | Egress receipts: content-free, hash-chained, receipt-before-send | `egress-receipt.py`, `llm.py` |
| gstack | MEDIUM findings block on a **non-interactive** write path | `_lib.py: guard_free_text` — fixed a live gap |

### A.3 Refused, with the reason

| Refused | Why |
|---|---|
| ECC's inlined plugin-root resolver (~900 chars of `node -e` in *every* hook command) | It exists to support six legacy install layouts we do not have. Ours is `lib/paths.js`, called once, with manifest commands one line each. |
| `mergeHookStdout` — merging hook output as strings | We already do this better: handlers return `{decision, reason, context}` and only the runners serialize, so a deny anywhere wins structurally. Moving to string merging would be a regression. |
| ECC's 286-skill / 68-agent catalog | ~20× over our discovery ceiling. The standing rule is patterns, not catalog. |
| gstack's ~60-skill catalog and browser plane | Same reason, plus an entire second product. Our SDLC scope ends at the PR. |
| ECC's `RULES.md` always-loaded layer | A third always-on context layer by another name. We have governed homes for that content already: `templates/<stack>/` on stack match, `contexts/` on mode. |
| gstack's 160 KB SKILL.md soft ceiling | Correct for them, meaningless for us: our eager ceiling is 18,000 **chars**, so a 160 KB warning could never fire. A guardrail that cannot trigger is noise in a config file. |
| Multi-harness adapters | v3.1 targets Claude Code only. ECC marks every non-Claude target Partial or Beta, and maintaining thirteen adapters is visibly the largest tax in that repo. |

### A.4 Where we are ahead — do not regress these

The study was explicitly asked where our build already leads, so that importing a weaker
version of something would be caught:

- **Hook registration is declarative and single-sourced.** Our commands are one clean
  line and all wiring lives in `hooks/runtime/registry.json`. ECC repeats a ~900-character
  resolver per hook entry.
- **The enforcement plane is larger and is the harder bet.** 16 executing handlers behind
  `registry.json` + `dispatch.js` + `flags.js`. gstack's entire Claude-host hook surface
  is four hooks. These are different bets; ours is the one that is hard to retrofit.
- **`userConfig` reaches into the product**, not just hook on/off — a numeric gate
  threshold, a grounding toggle, an overlay profile — and each description carries its
  semantics inline where the schema has no enum.
- **The organization overlay has per-target merge semantics** (globs merged rather than
  replaced for `tool-registry.json`), recorded per repo as `overlayProfile`. gstack's
  overlay concept covers model-family prose only.
- **`respond.merge` is structural**, so a deny or block anywhere in a dispatcher wins by
  construction rather than by string precedence.

### A.5 What the study says to build next

Beyond §9's P0/P1, three mechanisms are worth taking and are not yet in:

1. **`ORCHESTRATOR_DRY_RUN=1`** — print which hooks *would* fire, with profile and target,
   without running them. ECC has this in both runners and it is the fastest way to answer
   "why did nothing happen?".
2. **A file-based managed profile.** `flags.js` reads env vars only; ECC falls back to a
   `setup.json` under the plugin root, which is how an org sets a fleet-wide hook profile
   without touching anybody's environment. Directly relevant to a centrally distributed hub.
3. **`PostToolUseFailure` binding for MCP health.** Ours can only learn from its own probe;
   binding the same handler to the failure event marks a server unhealthy after a *real*
   failure, which is what makes the declared fallback reachable in practice.

---

*The SDLC core is unchanged. What changed is who runs it — the platform, instead of a*
*runtime we had to build because the previous platform had none — and what it is allowed*
*to do, which is now written down as policy instead of assumed.*

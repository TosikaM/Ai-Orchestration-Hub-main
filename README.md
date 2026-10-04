# AI Orchestrator Hub

A centralized, technology-agnostic AI SDLC orchestrator that ships as a Claude Code
plugin: one hub repository, seventeen skills, ten agents, twenty-eight commands, and
sixteen hooks that can refuse a tool call.

Version 3.1.0 — `hub.config.json`.

---

## What you can do with it

- **Take a requirement from plain language to a pull request** through a six-phase
  pipeline that checkpoints after every gate, runs review and test in parallel, and stops
  at human gates the agent cannot clear for itself.
- **Ask about an unfamiliar repository and get an answer whose files and symbols were
  checked before they were named.** Anything the index cannot confirm comes back as
  `NOT FOUND` rather than as a confident sentence about a file that does not exist.
- **Stop the first edit to a file until somebody has established its blast radius.** The
  fact-forcing gate denies that edit and asks for the importer list, the affected exports,
  the persisted shapes, and your own instruction quoted back. Present the facts and retry;
  the same file is never gated twice in a session.
- **Turn a pile of client documents into requirements you can cite.** `knowledge/` ingests
  PDFs, Office files and screenshots into extracted Markdown that keeps a page, slide or
  sheet anchor, and `context/` synthesises them into a project brief where every claim
  carries a provenance comment back to the source.
- **Carry one requirement across four repositories without the names drifting.** The band
  protocol fixes the execution order producers-first and hands each downstream repository
  the upstream contract to consume as named.
- **See what a session costs you before you type, and get a ranked list of reductions.**
  `python scripts/context-bill.py` prints the always-on bill and the per-invocation bill
  separately, because a kilobyte in the first column is not the same expense as a kilobyte
  in the second.

---

## Quick Start

Install the plugin once per machine:

```
/plugin marketplace add abhishek-narula-algoworks/Ai-Orchestration-Hub
/plugin install orchestrator@algoworks
```

Bootstrap each repository you want the orchestrator to understand:

```
/orchestrator-init
```

That generates `.github/orchestrator-context.md` — the layer map, stack detection, and
conventions the agents read — and records what it wrote in
`.github/orchestrator-install.json`. Those two files are the only paths written into a
consumer repository; everything else lives in the plugin.

Then confirm the install is actually healthy rather than assuming it:

```
python scripts/orchestrator.py doctor
```

`doctor` exists because several readers in this system fall back to built-in defaults when
their config file is unreadable. A repository whose `config/` failed to sync runs on
defaults silently and forever, and `doctor` is the only thing that would ever say so.

**Optional — the view plane.** A slim VS Code extension in `view/` renders pipeline state,
pending human gates, connected repositories, and the memory store as tree views, and gives
the gate panel a button. Package it with `vsce package` from `view/` and install the
resulting `.vsix` through *Extensions → Install from VSIX*. It is genuinely optional:
`python scripts/pipeline.py approve <pipelineId> <phase>` writes the identical verdict
file, so a terminal-only user is fully served.

---

## Prerequisites

| Requirement | Why it is required |
|---|---|
| **Claude Code 2.1 or later** | The plugin mechanism and the `PreToolUse` `permissionDecision` contract. Recorded as `plugin.minimumClaudeCodeVersion` in `hub.config.json`. |
| **Node.js 18 or later** | Every hook handler under `hooks/runtime/` is plain Node reading a JSON payload on stdin. No Node, no gates. |
| **Python 3.11 or later, with `pyyaml`** | Every CLI in `scripts/` and the eval runner are Python. `pyyaml` is the only third-party dependency in the content plane, deliberately — `pip install pyyaml`. |
| **`git` on the PATH** | The install lifecycle, the diff-selected eval harness, and `skip-worktree` handling all shell out to it. |

Two of these fail quietly, which is why they are stated rather than assumed.

**Without Node, the hooks do not fire and nothing says so.** Claude Code runs the handler,
the process exits non-zero, the hook contributes no decision, and the session continues
exactly as though the gate had allowed the action. The protection is gone and the
reassurance remains. If you want to check, run `node --version` and then make a trivial
edit in a connected repository: the fact-forcing gate should stop you once.

**Without Python, the plugin still loads.** Skills, agents and commands are Markdown and
are discovered natively, so the system looks installed. What breaks is everything the
skills call out to: the structural graph, the grounding manifest, the memory store, the
pipeline scheduler, the context bill. Skills will describe steps that then fail.

---

## Architecture: three planes

```
                          ┌───────────────────────────────────────┐
                          │            CONTENT PLANE              │
                          │          the Markdown brain           │
                          │                                       │
                          │   agents/ (10)      skills/ (17)      │
                          │   commands/ (28)    contexts/ (3)     │
                          │   prompts/ (28)     instructions/ (2) │
                          │   memory/ (4 tiers) knowledge/        │
                          │                                       │
                          │   GENERATED from content-src/ by      │
                          │   scripts/gen-content.py              │
                          └───────────────────┬───────────────────┘
                                              │  contributed by the plugin manifest
                                              │  and discovered natively
                          ┌───────────────────▼───────────────────┐
                          │            RUNTIME PLANE              │
                          │      Claude Code itself, ≥ 2.1        │
                          │                                       │
                          │   .claude-plugin/plugin.json          │
                          │   .claude-plugin/marketplace.json     │
                          │   hooks/hooks.json                    │
                          │                                       │
                          │   hooks/runtime/  16 handlers         │
                          │        PreToolUse can DENY            │
                          │   scripts/        the Python CLIs     │
                          └───────────────────┬───────────────────┘
                                              │  writes state files
                                              │  ~/.orchestrator/ and memory/sessions/
                          ┌───────────────────▼───────────────────┐
                          │             VIEW PLANE                │
                          │   view/ — a slim VS Code extension    │
                          │                                       │
                          │   READS state files. Owns no          │
                          │   orchestration. Writes exactly one   │
                          │   thing: a human-gate verdict.        │
                          │   Optional in every workflow.         │
                          └───────────────────────────────────────┘
```

The arrows run one way, and that is the point. The content plane does not know the runtime
exists; it is Markdown that another harness could read. The runtime plane owns every
decision. The view plane can be deleted without changing a single outcome —
`check_plane_separation` in `scripts/validate-structure.py` fails the build if anything in
`view/src/` writes to disk other than the gate verdict.

Note that `hooks.json` lives at `hooks/hooks.json`, beside the `*.hook.md` documentation
files, not under `.claude-plugin/`. `check_no_hooks_in_plugin_manifest` in
`scripts/validate-structure.py` enforces that `plugin.json` carries no `hooks` key, so the
two never end up disagreeing about which file registers a hook.

---

## The SDLC lifecycle

Six phases, expressed as a DAG in `config/pipeline-graph.json` rather than as an array,
because the protocol always described review and test running in parallel and a flat array
could not do that. Here they are siblings and `deploy` waits for both, so the parallelism
is a property of the data rather than a claim in a document.

```
   analyze  ──►  implement  ──┬──►  review  ──┐
   [HUMAN]                    │     gate 80   ├──►  deploy  ──►  complete
                              └──►  test   ───┘     [HUMAN]
                                    gate 80
                              ── parallel ──
```

| Phase | Agent | Skill | Quality gate | Human gate |
|---|---|---|---|---|
| `analyze` | `analyst` | `repo-context-builder` | — | **Yes** |
| `implement` | `developer` | `cqrs-developer` | — | No |
| `review` | `reviewer` | `quality-sentinel` | 80 / 100 | No |
| `test` | `qa` | `quality-sentinel` | 80 / 100 | No |
| `deploy` | `orchestrator` | `release-engineering` | — | **Yes** |
| `complete` | `orchestrator` | `continuous-learning` | — | No |

**Review and test genuinely run in parallel.** They are activated together when
`implement` completes, they score independently, and `deploy` activates only when both
have passed their gate. Three consecutive gate failures on one phase escalate rather than
loop.

**The human gates are gates, not notifications.** The phase writes a review artifact and
stops. A `Stop` hook then refuses to let the session end while a gate artifact exists with
no matching verdict file. The agent cannot write its own verdict, and the verdict is
ordinary JSON on disk written either by the view plane's gate panel or by
`python scripts/pipeline.py approve <pipelineId> <phase>`. A gate whose entire
implementation is a toast notification is a request; this one uses the same insight as the
fact-forcing gate — own the action stream, not the generation stream.

Every gate checkpoints, and so does pre-compaction, so `python scripts/pipeline.py resume
<pipelineId>` picks up a run that a compacted context window interrupted.

---

## How dispatch works now

There is no router. There used to be: the predecessor architecture shipped a VS Code
extension that registered a chat participant, mapped command names to skills in
TypeScript, loaded the Markdown itself, and assembled the prompt. All of that is deleted,
because the host already does it.

**Skill discovery is native.** `.claude-plugin/plugin.json` points at `./skills/`,
`./agents/` and `./commands/`. Claude Code parses each `SKILL.md` frontmatter — `name` and
`description` only — and loads the body when it decides the skill applies. The description
is therefore the entire routing surface, which is exactly why it is budgeted at 240 bytes
per skill: it is loaded in every session in every repository before anyone types.

**Slash commands are files.** `/review` is `commands/review.md`, which names the skill it
requires and does not restate the protocol.
`check_command_skill_parity` in `scripts/validate-structure.py` fails the build if a
command resolves to a skill that does not exist, or if a skill contributes a command file
that no top-level command was generated for. A command mapped to nothing is a slash
command that silently does the default thing.

**Enforcement is hooks, not prose.** `hooks/hooks.json` registers commands that
run `hooks/runtime/run.js <hook-id>` (or `dispatch.js <dispatcher-id>` for the batched
`Stop` phase). A `PreToolUse` handler returns `permissionDecision: "deny"` and the tool
call does not happen. That is the whole architectural change: the system does not own the
generation stream and never claimed to, but it owns the **action** stream — which is where
a hallucination stops being a sentence and becomes an edit.

**Three enforcement profiles.** `hooks/runtime/registry.json` defines `minimal`,
`standard` and `strict`, so a repository can dial the gates down without editing a
handler. Two guards are pinned outside the profile system — prompt defense and the memory
redaction guard — because a convenience dial should not double as a security dial.

**Natural language still reaches the right skill,** because each `SKILL.md` carries a
`## Routing` block with triggers, a `USE FOR` list, and a `NOT FOR` list that must name its
destination. `NOT FOR: writing code` is useless; ``NOT FOR: writing code — that is
`cqrs-developer` `` routes correctly, and the validator enforces the difference.

---

## Command reference

Twenty-eight commands. The skill column is the file the command requires; `/mode` and
`/doctor` mutate session or install state instead and own no skill.

| Command | Skill | What it does |
|---|---|---|
| `/orchestrator-init` | `repo-context-builder` | Bootstrap or refresh this repository's context and register it with the hub. |
| `/sdlc-start` | `sdlc-orchestrator` | Run the full pipeline from requirement to pull request. |
| `/plan` | `sdlc-orchestrator` | Phases 0–2 only: classify, stories, impact analysis, risks, unknowns. |
| `/pipeline` | `sdlc-orchestrator` | Show, resume, approve or abandon a running pipeline. |
| `/document` | `sdlc-orchestrator` | Documentation, release notes and changelog entries from what the pipeline produced. |
| `/analyze` | `repo-context-builder` | Deep analysis — trace a field or feature through every architectural layer. |
| `/explore` | `repo-context-builder` | Fast read-only investigation, confidence-tagged, with an explicit not-examined list. |
| `/implement` | `cqrs-developer` | Implement a change following this repository's conventions, then verify it. |
| `/review` | `quality-sentinel` | Code review scored 0–100 against conventions, edge cases and the quality gate. |
| `/test` | `quality-sentinel` | Generate unit and integration tests with edge-case coverage, then run them. |
| `/qa` | `quality-sentinel` | End-to-end specs and manual test cases for the user-visible paths. |
| `/verify` | `verification-loop` | The six-phase pre-PR gate: build, types, lint, tests, security, diff review. |
| `/security` | `security-review` | Security review of the diff — credentials, injection, subprocess, dependencies, agent surface. |
| `/adr` | `architecture-decision` | Frame a design decision with real tradeoffs and record it as an ADR. |
| `/release` | `release-engineering` | Release readiness verdict, release notes, changelog entry and rollback note. |
| `/git` | `git-workflow` | Move a verified change from working tree to pull request — branch, commit, push, PR. |
| `/graph` | `structural-graph` | Build, refresh or query the cached structural symbol index. |
| `/ground` | `grounding-guard` | Verify every claim in a draft against the codebase and annotate by confidence. |
| `/budget` | `context-budget` | Measure the context bill and produce a ranked list of concrete token reductions. |
| `/loop` | `autonomous-loop` | Run a bounded iterate-until-done loop behind the safety kernel. |
| `/memory` | `continuous-learning` | Query, promote or prune two-tier learning memory. |
| `/learn` | `continuous-learning` | Capture a durable lesson into memory, deduplicated and redacted. |
| `/repo` | `cross-repo-orchestration` | Switch, list or connect repositories; activate a group; inspect the band. |
| `/mcp-compose` | `mcp-tool-composer` | Compose a multi-tool MCP chain with per-step budgets and declared fallbacks. |
| `/knowledge` | `knowledge-base` | Ingest or query the curated knowledge base, with citations. |
| `/project-brief` | `knowledge-base` | Synthesise `context/` — domain model, features, screens, rules — from the distilled knowledge base. |
| `/mode` | — | Switch behavioural context between `dev`, `review` and `research`. |
| `/doctor` | — | Diagnose the orchestrator install in this repository and report what is wrong. |

---

## From client documents to cited requirements

The pipeline above changes code. This half of the system decides what the code should do,
and it exists because "the agent recalled a requirement" and "the agent cited one" are
different acts that look identical in a transcript.

```
knowledge/inbox/       the source documents, never edited
        │  python scripts/ingest-knowledge.py extract
        ▼
knowledge/extracted/   Markdown that keeps <!-- page: N --> / <!-- slide: N --> anchors
        │  curation by topic — judgment, not a script
        ▼
knowledge/distilled/   one file per topic, conflicts flagged
        │  python scripts/ingest-knowledge.py index
        │  (or `refresh` to run extract + index together)
        ▼
knowledge/index/       knowledge-index.json — anchors, digests, conflict count
        │  /project-brief, run by the BA and analyst agents
        ▼
context/00-overview.md … 07-decisions.md
```

**Two artifacts, and conflating them is the mistake.** `knowledge/` is the source of
record: extracted, curated, never interpreted, and answerable with an anchor back to page
14. `context/` is the *interpretation* — the domain model, the features, the screens, the
rules — and every claim in it carries an inline `<!-- from: knowledge/distilled/... -->`
comment. `python scripts/project-context.py check` fails when a populated section has no
such citation, and separately fails when the open-questions file records none, because a
synthesis with nothing unresolved in it has usually stopped asking rather than finished.

Extraction refuses rather than partially ingests: the redaction scan runs on the way in,
and a HIGH-tier finding rejects the whole document. Images are never silently
"extracted" — `inventory_image` writes a stub marked `awaiting-description` that a model
must fill in, so a screenshot cannot become a confident sentence about a screen nobody
looked at.

**The corpus lives in the plugin and every repo reads it.** The plugin is installed once
per machine, so a developer standing in an application repo can cite the same knowledge
base without that repo carrying a copy that then drifts. `ingest-knowledge.py` falls back
to the plugin's corpus when the current repo has none, and says so on stdout rather than
answering silently from a corpus you did not expect; a repo that has its own distilled
knowledge keeps using it. Reads may fall back, writes never do — `extract` and `index`
refuse to write into the shared plugin from a consumer repo, because that would edit every
repository's corpus at once.

The trade, stated plainly: the knowledge base is no longer scoped to one project. With a
second client's material present a query would match across both, and the confidentiality
boundary becomes whoever can install the plugin. That is a deliberate choice for a
single-client corpus and it should be revisited before a second one is ingested.

When documents are added, `python scripts/ingest-knowledge.py refresh` runs extraction and
indexing in one step and reports what moved — curation still happens by hand in between,
so `refresh` tells you when topics are waiting for a human rather than inventing them. An
installed plugin caches by version, so a refreshed corpus reaches it only after a version
bump and a reinstall.

`python scripts/doc-graph.py` maps which document cites which, and answers the two
questions that matter for a corpus: `orphans` (curated but never cited by the synthesis)
and `dangling` (cited but does not exist). It is deliberately separate from
`scripts/graph.py`, which indexes code and has no concept of a document or an anchor.

---

## The governance subsystems

Each of these is a CLI plus a config file, and each exists because a specific failure was
observed rather than anticipated.

| Subsystem | Entry point | What it is for |
|---|---|---|
| **Policy engine** | `scripts/policy.py`, `config/policy.json`, `lib/policy.js` | Resolve what a given agent is permitted to do in a given repository — autonomy level, which gates apply, which capabilities are granted. `policy.py explain` says why, not just what. |
| **Decision memory** | `scripts/decision.py` | An append-only, event-sourced log of what was decided and why, with `supersede` and `redact`. The other memory tiers store facts and patterns; none stored decisions, so agents kept re-proposing rejected ones. |
| **Architecture baseline** | `config/architecture-baseline.json` | What a **new** project should be, per stack, across 17 stacks. Deliberately separate from `config/stack-mappings.json`, which answers the opposite question — what *is* this repo? Detection is a measurement; a baseline is a decision. |
| **LLM gateway** | `scripts/llm.py`, `config/model-pricing.json` | The headless path to a model: routing table, auth, retries, cost tracking. `llm.py doctor` answers whether a model is reachable at all. |
| **Egress ledger** | `scripts/egress-receipt.py` | A hash-chained, content-free record of attempted off-machine sends. Stated plainly: forensic observability, **not** an exfiltration control. It catches carelessness, which is the 99% case. |
| **Agent-surface audit** | `scripts/audit-agent-surface.py` | Audits what the orchestrator wrote *into a consumer repository*. That text is the highest-privilege content there, because it reaches a model's instructions with no human reading it first. |
| **Release cutting** | `scripts/release.py` | Bumps the version in the three files that carry it and proves none drifted. The marketplace resolves an install by the catalog version while the plugin reports its own, so a partial bump fails silently. |

---

## Token economy

Five budgets, each with a different unit of cost, and conflating them is how a budget
becomes theatre. They live in `config/token-budgets.json`, which is data: changing a
ceiling changes runtime behaviour with no code edit.

| Budget | What it covers | Ceiling | Paid |
|---|---|---|---|
| **Discovery** | `name` + `description` in every skill's frontmatter | 240 B per skill, 4,000 B aggregate | Every session, in every repository, before you type |
| **Eager** | One invocation's assembled context across ten layers | 18,000 chars | Once per command |
| **Memory read** | How much of a monotonically growing store is injected | 6 instincts at confidence ≥ 0.7, 8 decisions | Every injection |
| **Session start** | What `SessionStart` injects unconditionally | 8,000 chars | Once per session |
| **MCP surface** | Connector tool descriptions, which are always-on context | 1 default connector, 30 tools | Continuously |

What makes this worth having is not the numbers; it is that each one is checkable.

**Every ceiling has recorded provenance.** `discovery.derivation` stores the measured
value, when it was measured, and which skill dominates the total — currently 2,031 bytes
across 17 skills, 49.2% under the ceiling, dominated by `git-workflow` at 145 B. Changing
the ceiling without re-measuring fails CI, so an increase is always a visible line in a
diff rather than a one-character edit nobody notices. That is the ratchet, and it also
runs backwards: after a reduction lands you re-measure immediately, the recorded value
ratchets down, and the win cannot silently erode.

**Ceilings are guarded against being quietly disabled.** If
`aggregateFrontmatterBytes` becomes the string `"4000"` after a bad merge, the comparison
stops comparing rather than failing — so `check_budget_provenance` asserts every ceiling is
an integer, and asserts that every layer with a cap also appears in the priority order,
because a layer with a cap and no priority entry is never sent to the model at all.

**There is an instrument.** `python scripts/context-bill.py` prints the bill; `--budget`
grades it and exits non-zero on a violation; `--diff` shows only what your branch changed.
Every figure is a characters-divided-by-four **estimate** and is labelled as one on every
rendering. This repository does not publish a token-savings percentage, because nothing
here measures one. A predecessor claimed a specific figure in two places with no
measurement anywhere in the source; that number was deleted rather than propagated.

The eager layer sums to more than its total on purpose. Allocation is greedy in priority
order and trims the tail, so a large `SKILL.md` borrows headroom from layers that came in
short — the alternative is shrinking every layer uniformly until none of them is useful.
And blowing the eager budget warns rather than halts: a trimmed prompt degrades an answer,
and stopping a developer's work over a budget would be the worse outcome.

---

## Grounding guarantees

Grounding is enforced at four points, and the four are not equally strong. Saying which is
which is the point of the table.

| Stage | Mechanism | Where | Strength |
|---|---|---|---|
| Pre-flight | Resolve every path- and symbol-shaped token against the filesystem and the structural graph; hand the model an `EXISTS` / `NOT FOUND` manifest before it answers | `scripts/grounding.py` | **Strong** |
| Pre-action | Deny the first `Edit` or `Write` per file per session until retrieved facts are presented | `hooks/runtime/handlers/fact-force.js` | **BLOCKING** |
| In-prompt | The Four Laws, the grounding contract, truncation markers, the confidence taxonomy | `content-src/preamble/` | Moderate — instruction-following, not enforcement |
| Post-hoc | Audit the finished response for uncited claims and append a gap list | `hooks/runtime/handlers/citation-guard.js` | Advisory — makes gaps visible; cannot unsay them |

The row that changed the architecture is the second one. Under the previous design the
strongest available action was advisory, because the runtime assembled a prompt and handed
it to a chat window it did not own — by the time the model produced text, the runtime had
already spent its only move. A `PreToolUse` hook does not need the generation stream. It
denies the tool call.

So the strongest claim this system can make is narrow and worth stating exactly: **what it
now prevents is an edit to a file whose blast radius the agent never established.** Not a
wrong sentence — a wrong edit.

### What is not guaranteed

- **A wrong claim about a file that does exist and was genuinely read.** The manifest is
  lexical: it verifies that a path resolves and a symbol is in the index, not that a
  sentence about them is true. Semantic verification is out of scope for a lexical index,
  and saying so is part of the design rather than a gap in it.
- **Self-assessment.** The four-question gate in `grounding-guard` is answered from the
  same context that produced the claim, which is close to worthless as a check. It catches
  what it catches; running it is not the same as having been checked. That is precisely why
  the fact-forcing gate demands *retrieved* facts — an importer list nobody can produce
  without actually searching.
- **A cross-repository contract wired to the wrong thing.** The band protocol prevents
  naming drift. It does not verify that a downstream repository consumed the contract
  correctly; that needs an integration test crossing the repositories, which this system
  does not run.
- **Evals as an absolute measure of quality.** Each of the 18 cases ships its rubric in the
  same invocation, so a passing case shows that the agent does the right thing when told
  what is being measured. Read the scores as a regression signal between runs of the same
  case.
- **A claim about a file whose write was denied.** A gate can refuse a create, and a
  session that treats the refusal as ordinary friction can go on to report the file as
  written. There is no ledger of successful writes for `citation-guard` to check such a
  claim against, so this one is open rather than solved.
- **Gates that are switched off.** `ORCHESTRATOR_HOOKS_ENABLED=false` disables the whole
  runtime by design, and a missing Node runtime disables it by accident. Two guards ignore
  the profile system — prompt defense and the memory redaction guard — because a
  convenience dial should not double as a security dial, but the global kill switch still
  works. One obvious switch, not a hidden one.

---

## Repository structure

```
.claude-plugin/          plugin.json · marketplace.json — the distribution surface
agents/          (10)    generated  ─┐
skills/          (17)    generated   │  the content plane.
commands/        (28)    generated   ├─ Every one of these is rendered from
prompts/         (28)    generated   │  content-src/ by scripts/gen-content.py.
contexts/         (3)    generated   │  Do not hand-edit a file with the banner.
instructions/     (2)    generated  ─┘
content-src/             the .tmpl sources and the composable preamble/ blocks
hooks/                   hooks.json — what Claude Code registers — plus one *.hook.md
                         documentation file per hook
hooks/runtime/           run.js · dispatch.js · flags.js · registry.json · handlers/ (16)
lib/                     config.js · paths.js · state.js · redact.js · policy.js
scripts/                 the Python CLIs and the PowerShell install scripts
config/                  token-budgets · pipeline-graph · stack-mappings · tool-registry ·
                         redaction-patterns · install-profiles · policy ·
                         architecture-baseline · model-pricing — data, not code,
                         each with a *.schema.json beside it
memory/                  shared/ · repos/ · decisions/ · sessions/ — four tiers, plus
                         index/ derived from them
knowledge/               inbox → extracted → distilled → index
context/                 the synthesised project brief, 00-overview … 07-decisions
registry/                connected repositories and the active session
sync/                    the default sync config and its schema
evals/                   evals.json (18 cases) · touchfiles.json · eval-runner.py
templates/               per-stack pattern libraries: angular · dotnet · node · python · generic
overlays/                org-specific content merged over the neutral plane at sync time
migrations/              numbered upgrade scripts, applied by orchestrator.py upgrade
view/                    the VS Code view plane — reads state, owns no orchestration
docs/adr/                architecture decision records
docs/assessment/         corpus and build assessment reports
hub.config.json          org identity, hub version, plugin install coordinates
orchestrator-hub.yml     the hub marker file — a declaration of shape, not runtime config
```

---

## Working on the hub itself

`package.json` wraps the common CLIs; the Python form underneath is identical. Read
`CLAUDE.md` before your first change — most of `agents/`, `skills/`, `commands/`,
`prompts/`, `contexts/` and `instructions/` is **generated**, and hand-editing a file
carrying the generated banner silently forks it from its template.

| Task | Command |
|---|---|
| Full local build — generate, then validate | `npm run build` |
| Validate only — must exit 0 | `npm run validate` |
| Regenerate content · fail on drift | `npm run gen` · `npm run gen:check` |
| Context bill · fail over budget | `npm run bill` · `npm run bill:check` |
| Discovery budget: re-measure · verify | `npm run budget` · `npm run budget:check` |
| Diagnose the install in this repo | `npm run doctor` |
| Gate-tier evals | `npm run evals:gate` |
| One eval by id | `python evals/eval-runner.py --case eval-003` |

The VS Code extension has its own toolchain and the root scripts do not cover it: from
`view/`, `npm run typecheck`, `npm run bundle` (esbuild), `npm run package` (vsce).

---

## Documentation

| Document | Read it when |
|---|---|
| [`ARCHITECTURE-AND-SETUP.md`](ARCHITECTURE-AND-SETUP.md) | You want the design principles, the deployment reasoning and what it cost, the memory and token architectures in depth, the hook runtime, the band protocol, and the install lifecycle. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | You are adding a skill, an agent, a stack or a memory entry, or you are about to open a pull request. |
| [`SECURITY.md`](SECURITY.md) | You are assessing this tool's threat model, or you have something to report. |
| [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) | You want to know which patterns came from where, and what is adapted versus derived. |
| [`CLAUDE.md`](CLAUDE.md) | You are Claude Code, working on this repository. It loads in every session here. |
| [`memory/README.md`](memory/README.md) | You want the memory tiers, the confidence arithmetic and the promotion rule. |
| [`knowledge/README.md`](knowledge/README.md) | You are ingesting client documents and want the inbox-to-distilled contract. |
| [`docs/DEPLOY-STEPS.md`](docs/DEPLOY-STEPS.md) | You are deploying the hub and want the ordered steps. |
| [`docs/CLAUDE-DEPLOYMENT-AND-DESIGN.md`](docs/CLAUDE-DEPLOYMENT-AND-DESIGN.md) | You want the deployment and design reasoning in one place. |
| [`docs/assessment/`](docs/assessment/) | You want the recorded assessments of the ingested corpus and of the first end-to-end build. |

### Architecture decision records

| ADR | Decision |
|---|---|
| [`0001`](docs/adr/0001-claude-plugin-as-runtime.md) | The runtime is a Claude Code plugin, not a VS Code extension — with the strongest argument against it stated. |
| [`0002`](docs/adr/0002-sixteenth-skill-knowledge-base.md) | Adding `knowledge-base` as its own skill rather than folding ingestion into an existing one. |
| [`0003`](docs/adr/0003-gates-fail-closed-on-unreadable-input.md) | A gate that cannot read its input denies rather than allows. |

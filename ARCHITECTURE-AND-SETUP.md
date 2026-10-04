# Architecture and Setup

The deep document. `README.md` is what to do; this is why it is shaped that way, and what
each shape cost.

---

## 1. Design principles

These are the load-bearing decisions. When anything else in this repository is ambiguous,
resolve toward these.

| # | Principle | What it means in practice | The failure it prevents |
|---|---|---|---|
| **P1** | Token economy is a first-class constraint, **enforced rather than aspirational** | Five named budgets in `config/token-budgets.json`, each with a recorded derivation, checked in CI, with a CLI that prints the bill | A system that claims to optimize context and cannot produce a number. A principle nothing measures is a slogan. |
| **P2** | Grounding beats fluency | Every layer carries an evidence obligation: the pre-flight manifest, the fact-forcing gate, the preamble contract, the citation audit | An orchestrator that confidently describes code that does not exist. An honest "not found" outranks a plausible guess. |
| **P3** | Organization identity is data, not code | Any string naming a company lives in `hub.config.json` or under `overlays/`. Nothing else. A CI grep gate enforces it. | A hub that cannot be reused by another team without a find-and-replace, and a de-branding that is cosmetic rather than structural. |
| **P4** | Progressive disclosure | `SKILL.md` carries the protocol; bulk material lives in sibling `references/` files loaded only on demand | A skill that always loads twelve kilobytes of recipes it uses five percent of the time. That is a design failure, not a rich skill. |
| **P5** | Fail closed on safety, fail open on convenience | Quality gates, security findings and human gates block. Telemetry, dashboards and staleness hints warn and continue. | A nice-to-have taking down a pipeline. Also its mirror: a safety gate that degrades to a warning because warnings are easier. |
| **P6** | One source of truth per fact | Budgets in `config/token-budgets.json`. Pipeline shape in `config/pipeline-graph.json`. Hook wiring in `hooks/runtime/registry.json`. Org identity in `hub.config.json`. Shared directives in `content-src/preamble/`. | The single most common way this system rots. Two copies of a fact are two facts, and the one that drifts is always the one nobody runs locally. |

P6 extends to code that *reads* a fact, which is why `scripts/_lib.py` exists as one
module rather than six scripts with six slightly different frontmatter parsers. The day
they disagree is the day a budget check passes on a file the skill loader rejects.

---

## 2. The three planes, and why they are separate

### Content plane — the Markdown brain

`agents/`, `skills/`, `commands/`, `prompts/`, `contexts/`, `instructions/`, `memory/`,
`knowledge/`. Plain Markdown with YAML frontmatter, generated from `content-src/` and
readable by anything that can read Markdown.

This plane is deliberately inert. It contains no logic, calls nothing, and knows nothing
about the harness that will load it. That is what makes the whole system portable in the
one direction that matters: if the runtime has to be replaced, the brain does not move.

### Runtime plane — Claude Code itself

`.claude-plugin/` declares the plugin; `hooks/runtime/` holds fifteen handlers; `scripts/`
holds the Python CLIs the skills invoke. The plugin contributes skills, agents, commands
and hooks to a host that already knows how to load them, and the host provides skill
discovery, command routing and content distribution as primitives.

### View plane — a slim VS Code extension

`view/` renders state files: pipeline checkpoints, pending human gates, the connected
repository registry, the memory store. It reads. The single exception is the human-gate
verdict, which it may write, and that call site must carry a `gate-verdict-write` comment
or `check_plane_separation` in `scripts/validate-structure.py` fails the build.

### Why the separation is enforced rather than encouraged

Because the last architecture did not enforce it and the boundary dissolved. When the view
layer is also the runtime, every new capability has a plausible home in the editor, and
each one is individually reasonable: it already has the state, it already has a window, it
is already running. The result was twelve services of which roughly five re-implemented
platform primitives.

A checkable boundary makes "does this belong in the view plane?" a question with an
answer. If the view plane ever genuinely needs orchestration logic, that is the signal the
boundary was drawn in the wrong place — not a reason to widen the check.

---

## 3. The deployment decision

Recorded in full, with the options analysis, in
[`docs/adr/0001-claude-plugin-as-runtime.md`](docs/adr/0001-claude-plugin-as-runtime.md).
The summary and the honest ledger follow.

### What changed, mechanically

The predecessor shipped a VS Code extension as the runtime. Its own documentation stated
the central limitation, and the wording is worth quoting because it is the whole reason
this decision exists: the runtime **"does not own the generation stream."** Grounding was
therefore rated Strong, Moderate and Advisory, and the last of those **"cannot block."**

Every word of that was true. An extension that assembles a prompt and hands it to a chat
window has already spent its only move by the time the model starts producing text.

A Claude Code `PreToolUse` hook runs before a tool executes and returns a
`permissionDecision` of `"deny"`. That does not require owning the generation stream. It
owns the **action** stream, which is where a hallucination stops being a sentence and
becomes an edit. The reasoning is recorded at the point of use in
`hooks/runtime/handlers/fact-force.js`.

### Why a plugin rather than the alternatives

| Option | Why not |
|---|---|
| **A symlink script** into `~/.claude/skills/` | Everything the plugin mechanism does for free becomes ours: detecting which links we own so an uninstall does not delete a colleague's skills, pruning orphans after a rename, resolving name collisions between sources, Windows symlink semantics, and a migration path for every layout change. **Retained as a documented secondary path** for air-gapped machines and for teams that must pin an exact hub revision. |
| **An npm package** | A second identity, a second registry, a second credential set, and a second place a version number can be wrong. It does not remove the placement-and-removal work; it wraps it in a package manager. One private organization repository needs one identity. |
| **A committed `.claude/` per repository** | The hub is duplicated into every repository and every copy drifts on its own schedule. Choosing this as the primary mechanism would leave us maintaining a distribution system that distributes nothing. **Retained for per-repository overrides**, which is what a repository-local `.claude/` is genuinely good at: one team's extra hook, expressed where it applies and nowhere else. |
| **Keeping the extension as runtime** | Superseded rather than argued down. The mechanism its central limitation was stated against no longer holds. |

### What is genuinely lost

Two things got worse, and pretending otherwise would make the rest of this document less
trustworthy.

**1. The single `@orchestrator` mention.** A chat participant is one addressable name;
sixteen skills is a flatter surface, and a user who does not know which skill they want has
more to scan.

*Mitigation:* one router skill named `orchestrator` whose entire job is intent detection
and delegation, plus a `## Routing` block in every `SKILL.md` whose `NOT FOR` clauses must
name a destination skill. The routing content exists; what is lost is the single obvious
front door, and a `NOT FOR` list is a weaker affordance than a name you can type.

**2. Guaranteed context injection.** The extension's invocation path *always* streamed
repository context, memory and the evidence manifest. A skill is loaded when the model
decides to load it, which is a probability rather than a guarantee.

*Mitigation:* `SessionStart` injects the small, high-value set unconditionally — active
decisions, context-file staleness, the discovery footprint — capped at 8,000 characters.
Everything else becomes *retrieved on demand* rather than pushed, and the fact-forcing gate
makes the retrieval mandatory at the moment it matters. That is arguably the better
pattern, and it is what P4 already argues for; it is still a change from *always* to
*when asked*, and a reader deserves to know which one they have.

### The strongest argument against the decision

This ties the system to one vendor's harness at a specific minimum version. Every
capability that makes this architecture better than its predecessor exists because Claude
Code provides it. If that surface changes shape, the gates stop firing — and a gate that
stops firing does not announce itself. The content plane is portable because it is
Markdown; the enforcement plane is not, and the enforcement plane is the reason the system
is worth having.

---

## 4. Memory management

Four tiers of durable state plus one derived index, one write path, and one arithmetic
that decides what leaves a single repository and enters every repository. The full
treatment is in [`memory/README.md`](memory/README.md); this is the architectural shape.

| Tier | Path | Scope | Retention | Synced to consumers |
|---|---|---|---|---|
| Shared | `memory/shared/` | All repositories | Permanent | Yes |
| Per-repo | `memory/repos/<name>/` | One repository | Permanent | Only that repository |
| Decisions | `memory/decisions/<slug>.jsonl` | One repository | Permanent, append-only | No |
| Session | `memory/sessions/` | One pipeline run | Discarded | No — git-ignored |
| *(derived)* Index | `memory/index/` | Derived | Rebuildable | No — git-ignored |

The store itself is `memory/index/entries.json`. The Markdown under `memory/shared/` is a
**rendering** of that JSON produced by `scripts/memory.py` — one source, two
representations. Hand edits to the rendered files are overwritten by the next render and
are not a supported way in.

The distinction that matters most is the first column against the last. A wrong entry in
`memory/shared/` is not wrong once; it is wrong in every connected repository, silently,
until somebody notices — and it arrives pre-endorsed by the system.

### The promotion rule

> **Effective confidence ≥ 0.7 AND observed in ≥ 2 repositories.** Both, never either.

The second condition does the work. A high-confidence lesson observed in one repository is
usually a fact *about that repository* — its build quirk, its naming habit, its one strange
service — wearing the costume of a general truth. The capturing agent's certainty is
evidence about the agent, not about the world.

Confidence has a source rather than being asserted: first capture is `0.4` (deliberately
below the floor, so no single observation can promote anything), reinforcement in a new
repository is `+0.15`, reinforcement in a repository already seen is `+0.05`, a
counter-example is `-0.25`, and age costs `-0.05` per ninety days applied at read time
only. Two new-repository reinforcements reach exactly 0.7, which is also the moment the
second condition is satisfied.

Promotion is a deliberate command (`python scripts/memory.py promote`), never a background
effect of capture, and when nothing qualifies the command names what each near-miss is
missing.

**Decay ranks; it never deletes.** A wrong decay rate that deleted would silently discard
useful learnings — an unrecoverable, invisible loss discovered only when an agent repeats a
mistake the system had already recorded. Because decay only ranks, a wrong rate costs an
entry a few positions in a digest and is correctable in one constant. Pick the failure mode
you can notice and undo.

### One write path

`scripts/memory.py` is the only way in, and there is no flag that skips its guard. Shared
memory syncs organization-wide, so a captured credential is a replication event rather than
a local mistake; and stored memory is re-injected into future prompts, which makes the
store an injection surface as well as a storage surface. Both scans **refuse the write**
rather than sanitizing it, because a silently redacted resolution reads as complete and
nobody goes back to fix it.

The guard is a function you must call rather than an event hook, and that is deliberate:
modeling it as an event would leave the write path unguarded on every occasion the event
failed to fire, turning a wiring bug into a security hole. The honest way to make a guard
non-optional is to make the call site the only way in.

---

## 5. Token economy in depth

### The five budgets

| Budget | Unit of cost | Ceiling | Why it is separate |
|---|---|---|---|
| `discovery` | Skill frontmatter `name` + `description`, in utf-8 bytes | 240 B per skill, 4,000 B aggregate | Paid unconditionally by every user in every repository on every conversation, before anyone types. The most expensive text in the repository. |
| `eager` | The assembled context for one invocation, in characters | 18,000 chars across ten layers | Paid once per command by the user who ran it. |
| `memoryRead` | Entries injected from a monotonically growing store | 6 instincts at confidence ≥ 0.7, 8 decisions | Shared memory grows; the eager layers do not. Without a read-side cap the digest truncates by recency, and recency degrades as a relevance proxy exactly as the store becomes valuable. |
| `sessionStart` | Everything `SessionStart` injects unconditionally | 8,000 chars | The most easily-bloated always-on surface there is — the one place "we load context automatically" quietly becomes "we spend tokens before you type." |
| `mcpSurface` | Connector tool descriptions | 1 default connector, 30 tools | Every MCP tool description is always-on context. A section whose premise is that always-on cost is the expensive kind cannot omit MCP from its accounting. |

The planning ratio is four characters per token, declared once as
`charsPerTokenEstimate`. Every figure derived from it is an estimate and is labelled as one
wherever it is printed.

### The eager allocation ladder

Ten layers, allocated greedily in a fixed priority order:

```
  1. skillMd               8,000
  2. commandFile           2,000
  3. evidenceManifest      1,200
  4. activeDecisions         900
  5. repoContext           2,500
  6. memoryAntiPatterns    1,500
  7. knowledgeDigest       1,000
  8. structuralGraph       2,000
  9. memoryBestPractices   1,500
 10. memoryToolChains      1,200
                          ──────
     sum of layers        21,800   ← deliberately over
     totalChars           18,000
```

**The overcommit is the design, not an error.** If the layer caps summed exactly to the
total, every layer would have to be trimmed uniformly whenever any one of them ran large,
and a uniformly trimmed context is one where no layer is useful. Because allocation is
greedy in priority order and trims the tail, a large `SKILL.md` borrows headroom from
layers that came in short. The cost is that low-priority layers are not guaranteed —
`memoryToolChains` may get nothing on an invocation with a very large skill — which is why
the order is explicit and why every capped layer must appear in `priority`. A layer with a
cap and no priority entry is never sent at all, and `check_budget_provenance` fails the
build on that exact orphan.

Overrun warns at 85 percent, appends an explicit truncation marker, records the overrun and
proceeds. `hardFail` is `false`, which is P5 in action: blowing the eager budget degrades
answer quality; it is not a safety incident, and halting a developer's work over a budget
would be the worse outcome.

### The ratchet protocol

A ceiling with no recorded provenance has three problems, all of which surface months
later. The number has no history, so the first person who needs three hundred more bytes
edits the constant and the ceiling is gone with no trace. A new skill defaults to allowed,
because there is no "this skill has never been budgeted" state. And nothing tests the test:
if `aggregateFrontmatterBytes` becomes a string after a bad merge, the comparison stops
comparing rather than failing.

So the ceiling carries a derivation block — `measuredValue`, `measuredAt`, `skillCount`,
`dominantSkill` — and three mutation pins in `scripts/validate-structure.py`:

1. **Every ceiling must be a real integer.** A string ceiling is a disabled ceiling wearing
   the costume of an enabled one.
2. **The recorded measurement must match reality.** Drift fails the build and prints the
   protocol.
3. **Every capped layer must be in the priority order and vice versa.**

The protocol itself:

| Situation | What to do |
|---|---|
| Growth that is a real feature | Re-run `python scripts/measure-discovery-budget.py` and commit the derivation block **in the same commit** as the change, so the reviewer sees the cost as a line in the diff. |
| Accidental growth | Do **not** re-measure. Fix the frontmatter: trigger text, `USE FOR` and `NOT FOR` belong in the `## Routing` body, not in the description. |
| A reduction landed | Re-measure immediately so the recorded value ratchets **down** and the win is locked in. |

`check_every_skill_is_budgeted` closes the last hole: a skill folder present on disk but
absent from `SKILLS` in `scripts/_lib.py` fails the build, because an unlisted skill is one
nobody has consciously budgeted.

---

## 6. Grounding architecture and its limits

Four enforcement points, of three different strengths.

| Stage | Mechanism | Implementation | Strength |
|---|---|---|---|
| Pre-flight | Extract path- and symbol-shaped tokens, resolve each against the filesystem and the structural graph, hand back an `EXISTS` / `NOT FOUND` manifest **before** the model answers | `scripts/grounding.py` | Strong |
| Pre-action | Deny the first `Edit` or `Write` per file per session until four retrieved facts are presented | `hooks/runtime/handlers/fact-force.js` | **Blocking** |
| In-prompt | Four Laws, grounding contract, confidence taxonomy, truncation markers, the claimed-limitations rule | `content-src/preamble/` rendered into every agent and skill | Moderate |
| Post-hoc | Audit the finished response for uncited claims and append a gap list | `hooks/runtime/handlers/citation-guard.js` | Advisory |

### Why forced retrieval rather than asked confidence

Asking a model "are you sure?" is answered "yes" by construction, because the same context
that produced the claim evaluates the claim. Forced *retrieval* is different in kind: an
agent cannot produce a file's importer list without actually searching, and the act of
searching creates the awareness that the question never did.

The gate therefore demands four facts before a first edit: every file that imports this
one; the exported functions, classes or types affected, each with `file:line`; the field
names and shapes if the file touches persisted data; and **the user's current instruction,
quoted verbatim**. The fourth is deliberately unrelated to the file — it is the drift
check, because forty turns into a session the goal being executed and the goal that was
given are not reliably the same thing, and nothing else in the system checks for that.

Three details keep the gate installed rather than switched off. It fires on **first touch
per file per session**, because gating every edit makes the tool unusable. Denials collapse
to a one-line ordinal after three full blocks, because an identical eight-line block
repeated ten times becomes wallpaper. And it offers **narrow recovery before broad** — a
path-scoped `ORCHESTRATOR_GATE_EXEMPT_GLOBS` before the `ORCHESTRATOR_GATEGUARD=off`
sledgehammer — because a gate that offers only "turn it all off" gets turned all off,
permanently, the first time it is inconvenient.

The compliance cost is unusually low, and that is not an accident. Fact 1 in a generic
repository means a manual tree walk; here `python scripts/graph.py importers <file>` reads
the cached symbol index. The gate is cheap to satisfy precisely because the orchestrator
already did the indexing work.

### The manifest never cries wolf

If nothing in a batch resolves, the whole batch is suppressed rather than reported as a
wall of `NOT FOUND`. A manifest that flags every capitalized word trains its reader to skip
it, and a skipped manifest is worse than no manifest, because the system still believes it
is grounded.

### The limits, stated

The manifest prevents describing a file that does not exist, calling a method a class does
not have, and silently continuing past a truncation. It does not prevent a wrong claim
about a file that does exist and was genuinely read — that needs semantic verification,
which is out of scope for a lexical index.

The four-question gate in `grounding-guard` is self-assessment, answered from the same
context that produced the claim. Use it to catch what it catches; do not mistake having run
it for having been checked.

---

## 7. The hook runtime

Fifteen hooks. The `.hook.md` file is the documentation half; the handler in
`hooks/runtime/handlers/` is the executing half; `hooks/runtime/registry.json` is the
single source of truth for wiring. `check_hook_runtime_parity` fails the build if any of
the three disagree, which is the check that would have caught five hooks shipping once as
Markdown that nothing executed and being counted in a capability inventory as a working
surface.

| Hook id | Event | Matcher | Profiles | Blocks |
|---|---|---|---|---|
| `pre:edit-write:fact-force` | PreToolUse | `Edit\|Write\|MultiEdit` | standard, strict | **Yes** |
| `pre:edit-write:config-protection` | PreToolUse | `Edit\|Write\|MultiEdit` | standard, strict | **Yes** |
| `pre:read:prompt-defense` | PreToolUse | `Read` | all — **profile-exempt** | No |
| `pre:bash:destructive-gate` | PreToolUse | `Bash` | standard, strict | **Yes** |
| `pre:mcp:health` | PreToolUse | `mcp__.*` | standard, strict | **Yes** |
| `session:start:bootstrap` | SessionStart | `.*` | all | No |
| `session:start:token-budget-guard` | SessionStart | `.*` | all | No |
| `pre:compact:checkpoint` | PreCompact | `.*` | all | No |
| `stop:citation-guard` | Stop | `.*` | standard, strict | No |
| `stop:human-gate` | Stop | `.*` | all | **Yes** |
| `stop:learning-capture` | Stop (async) | `.*` | all | No |
| `stop:context-staleness` | Stop (async) | `.*` | standard, strict | No |
| `stop:telemetry` | Stop (async) | `.*` | all | No |
| `session:end:teardown` | SessionEnd | `.*` | all | No |
| `memory:write:redaction` | In-process | — | all — **profile-exempt** | **Yes** |

Two entries in that table need their notes read rather than skimmed.
`session:start:token-budget-guard` is invoked in-process by `session-bootstrap` rather than
registered separately, so session start costs one Node process instead of two.
`pre:mcp:health` is registered in the manifest only when an organization enables a
connector, because a gate on a surface nobody uses is pure startup cost.
`memory:write:redaction` is not an event hook at all — it is the function called at the
memory write site, for the reason given in §4.

### Profiles and the kill switch

Three profiles, resolved in `hooks/runtime/flags.js`, most specific first:

1. `ORCHESTRATOR_HOOKS_ENABLED=false` — the global kill switch.
2. `ORCHESTRATOR_DISABLED_HOOKS=<csv of hook ids>` — surgical, per session.
3. The hook's declared profiles against the active profile: `minimal` is lifecycle
   bookkeeping only and nothing blocks; `standard` is the default and adds the grounding,
   config and destructive gates; `strict` adds the advisory passes that are noisy by
   design.

**An invalid profile falls back to `standard`, never to off.** A typo in a config value
must not silently disable every gate in the system; that is the failure mode where a guard
looks installed and is not.

**Two hooks ignore the profile system entirely.** Prompt defense and the memory redaction
guard are profile-exempt, because a profile is a convenience dial for friction and not a
security dial — turning them off by choosing a lighter profile would be a footgun disguised
as a preference. The hub distributes executable Markdown and shared memory syncs
organization-wide; those two channels do not get a friction discount. The global kill
switch still turns off the entire runtime, which is the point: one obvious switch rather
than a hidden one.

### The two Stop dispatchers

`Stop` fires five hooks, split across two dispatcher processes:

```
stop:dispatcher:sync    citation-guard → human-gate            timeout 15s
stop:dispatcher:async   learning-capture → context-staleness
                        → telemetry                            timeout 30s
```

**One Node startup for the whole synchronous phase beats six.** Process startup is paid per
hook, and on the `Stop` path it is paid at the exact moment the user is waiting to see a
finished answer. Six cold Node processes to run five small handlers is latency the user
attributes to the model.

Batching has a second effect worth naming: ten edits in one turn produce one staleness
check at Stop, not ten. And the split matters as much as the batching — learning capture
must never make the user wait, so the asynchronous dispatcher runs after the response is
delivered.

The requirement this imposes is that every handler exports `run(payload)` in addition to
its CLI entry. That was designed in from the first handler rather than retrofitted,
because retrofitting it later is a rewrite.

### Guarding the guards

`config-protection` denies edits to the files that define a quality gate. Nothing else
stops an agent from editing `config/token-budgets.json` to make a budget failure go away,
or a lint config to make a lint failure go away — and "the failure went away" is
indistinguishable in a transcript from "the problem was fixed."

---

## 8. The cross-repo band protocol

State lives at `~/.orchestrator/state/connected-repos.json`, outside any repository. It was
previously editor-scoped state, which meant the answer to "which repository am I in"
existed only inside one process. A file is readable from a terminal, from CI and from the
view plane, and nothing has to ask a running editor.

### The rule the band exists for

> **Upstream contracts must be consumed downstream as named.**

Renaming a field downstream because it reads better locally produces four repositories that
each compile and do not talk to each other. That is the characteristic failure of multi-repo
work, and it is always a naming drift, never a logic error.

### A worked example

The requirement: *"Add an `ImpactInvestment` amount to the donation flow so it shows on the
donation form, is stored, and appears in the quarterly report."* Four repositories.

**Step 1 — establish execution order, producers before consumers.**

```
shared-library  →  command-api  →  query-api  →  frontend
   (contract)      (writes it)     (reads it)    (shows it)
```

Get this backwards and the frontend compiles against a field the API has not shipped, which
passes CI in the frontend repository and fails in production.

**Step 2 — the band file**, `memory/sessions/pipe-m8x2k1.band.json`:

```json
{
  "requirement": "Add an ImpactInvestment amount to the donation flow",
  "executionOrder": ["shared-library", "command-api", "query-api", "frontend"],
  "completedRepos": [],
  "sharedContracts": {},
  "remainingRepos": ["shared-library", "command-api", "query-api", "frontend"],
  "pipelineState": "analyze"
}
```

**Step 3 — `shared-library` runs and records what it exposed.**

```json
{
  "repo": "shared-library",
  "changes": ["src/Models/Donation.cs", "src/Dto/DonationDto.cs"],
  "exposedInterfaces": [
    "Donation.ImpactInvestment: decimal?",
    "DonationDto.ImpactInvestment: decimal?"
  ],
  "buildStatus": "green",
  "notes": "Nullable so every existing row stays valid without a backfill."
}
```

Those interfaces are promoted into `sharedContracts` by
`python scripts/cross-repo.py band advance`.

**Step 4 — `command-api` receives the contracts as binding.** If it decides
`ImpactInvestmentAmount` reads better and renames locally: `command-api` compiles,
`query-api` compiles against the shared library's name, the two do not agree, and nothing
fails until a donation with that field round-trips. If the name is genuinely wrong, change
it in `shared-library` and re-advance the band. One extra pass, and the only correct move.

**Step 5 — the mapping mechanism is still per-repository.** The band carries the contract;
it does not carry the wiring.

| Repo | Mechanism | The thing that gets forgotten |
|---|---|---|
| `command-api` | AutoMapper profile | A new property needs no config **unless** the profile uses `ForMember` explicitly — then it silently maps to null. |
| `query-api` | Dapper read model | The SQL projection is hand-written. A new column is not automatic. |
| `frontend` | Reactive form | The form control, the interface **and** the template all need it. Two out of three compiles. |

**What blocks the band.** A repository whose build is not green does not advance, because
downstream work against a broken contract is worse than no work. A human gate anywhere
stops the whole band, not just that repository. A lock held by another session means
somebody else is already in that repository — wait, do not force. Locks expire after an
hour so a crashed session does not wedge a band permanently.

**The honest limit.** The band tracks contracts and order. It does not verify that a
downstream repository actually *consumed* the contract correctly; that needs an integration
test crossing the repositories, which this system does not run. What it prevents is the
drift. What it cannot prevent is a correct name wired to the wrong thing. Say so when
reporting a completed band.

---

## 9. The pipeline DAG and resume semantics

The shape lives in `config/pipeline-graph.json`. `review` and `test` are siblings of
`implement` and `deploy` waits for both, so parallelism is a property of the data rather
than a claim in prose. A phase activates when all of its parents are complete.

**Checkpoints.** Written after every gate and again on `PreCompact`, to
`memory/sessions/{pipelineId}.checkpoint.json`. The pre-compaction checkpoint is the one
that earns its keep: compaction is exactly when a long pipeline loses the state it needs,
and it happens without anybody deciding it should.

**Resume.** `python scripts/pipeline.py resume <pipelineId>` reads the checkpoint and
recomputes which phases are ready, rather than replaying from the start. `ready` prints
that set without changing anything, which is the command to run when you are not sure what
a half-finished pipeline is waiting for.

**Human gates.** The phase writes `{pipelineId}.gate-{phase}.md` and stops. A `Stop` hook
refuses to let the session end while an artifact exists with no matching
`{pipelineId}.gate-{phase}.json` verdict. The agent cannot write its own verdict. The
verdict being ordinary JSON on disk is what makes the view plane optional rather than
required: `pipeline.py approve` and the gate panel write the identical file, so anyone in a
terminal, on Linux, or in a different editor is fully served.

**Escalation.** Three consecutive gate failures on one phase escalate rather than loop,
because an agent that has failed the same gate three times is not one iteration away from
passing it.

---

## 10. Secret hygiene and the egress ledger

### The redaction taxonomy

One taxonomy in `config/redaction-patterns.json`, consumed by `scripts/redact.py`,
`lib/redact.js`, the memory write path and the generated release documentation. Three
tiers:

| Tier | Meaning | Behaviour |
|---|---|---|
| **HIGH** | A genuinely-secret credential | **Blocks** the write or the send. There is intentionally no per-pattern key to disable HIGH blocking. |
| **MEDIUM** | PII, legal or damaging content, an internal leak, or a credential shape with a high false-positive rate | Confirms with the user. |
| **LOW** | Hygiene | Surfaced only. No prompt, no block. |

The calibration rule is that a gate which cries wolf gets ignored, so only genuinely-secret
credentials are HIGH. **Repository visibility never promotes a tier**: a public repository
earns sterner per-finding confirmation on MEDIUM findings; it does not turn MEDIUM into
HIGH. Auto-promotion is how a gate becomes noise, and noise is how a gate gets switched
off.

Suppressions are scoped deliberately. The placeholder suppression matches the **matched
span**, not the line, so a real key on the same line as the word "example" still counts.
The test-fixture path suppression applies to MEDIUM and LOW only, because a HIGH-tier
credential in a test file is still a HIGH-tier credential — that is where they most often
get committed.

Every pattern must be linear-time; `python scripts/redact.py --lint` fails CI on a
catastrophic form. A regex that backtracks does not fail loudly, it hangs the egress path,
and the natural workaround is to disable redaction.

Sinks declare their own polarity rather than having it decided by the scanner:

| Sink | Polarity | Why |
|---|---|---|
| `memory.shared.write` | fail-closed | Syncs to every connected repository. |
| `memory.decision.write` | fail-closed | Re-injected into future prompts. |
| `context.file.write` | fail-closed | Committed in some repositories, and the densest artifact in the system. |
| `release.artifact.write` | fail-closed | Published. |
| `hub.clone` | fail-closed | Pulls executable content — `SKILL.md` files that steer agents. |
| `chat.stream` | fail-open | Blocking the user's primary interaction over a scan is the worse outcome (P5). |

### The egress ledger

`~/.orchestrator/security/egress.jsonl`, written by `scripts/egress-receipt.py`. Three
properties: the receipt is written **before** the send (fail-closed sinks refuse the send
if it cannot be written); it is **content-free**, holding a sha256 of the exact bytes and a
byte count and never payload text, because a ledger that stored payloads would itself
become the leak; and it is **tamper-evident**, each line carrying `prev` = sha256 of the
previous raw line, so a deletion or an edit is detectable without making the log immutable.

**The threat-model sentence, which is not optional:** this is **forensic observability, not
an exfiltration control.** It records what was attempted so an accident is auditable. A
determined leaker bypasses it trivially. What it catches is carelessness, which is the
common case and the case the redaction gate is also aimed at. Writing that down matters as
much as the code, because a ledger described as a security control will be trusted as one,
and then somebody will decide a second control is unnecessary "because we have the ledger."

---

## 11. The install lifecycle

`python scripts/orchestrator.py <command>`:

| Command | What it does |
|---|---|
| `list-installed` | Prints the hub, version, profile, overlay and every recorded operation. The answer to "what did you put on my machine?" |
| `doctor` | Verifies files, hashes, the managed gitignore block, `skip-worktree` bits, the hub version, config readability, the discovery footprint and context-file staleness. |
| `repair` | Re-derives the install from the recorded **request**, not from what is on disk. |
| `upgrade` | Runs the numbered migrations in `migrations/` in order, stopping at the first failure because later migrations assume earlier ones ran. |
| `uninstall --dry-run` | Prints the plan. The documented first step. |
| `uninstall` | Reverses exactly what the install state records. |

Only two paths are written into a consumer repository — `.github/orchestrator-context.md`
and `.github/orchestrator-install.json` — down from roughly ten under the previous model,
which is the single biggest simplification in this architecture. One of the old ten was the
whole `.github/instructions/` directory, which would have swallowed a consumer repository's
own instructions file. That class of bug goes away with the narrow list rather than being
guarded against.

**Why uninstall is the serious one.** A tool that writes into a team's `.github/` and offers
no removal path is a tool a senior engineer is right to refuse. "Delete the files yourself"
is not an uninstall when the tool also edited `.gitignore` and ran
`git update-index --skip-worktree` on tracked files — that last one is invisible state a
user cannot discover, let alone reverse, without already knowing the flag exists. So
`operations` in the install state records `gitignore-block` and `skip-worktree` as
first-class operations alongside file writes; those two are exactly what an uninstall must
reverse and exactly what a file listing would miss.

**The ownership gate.** Uninstall removes only what the install state records as written by
us, verified by sha256. A foreign file at a path we would have used is named in the output
and left alone, and so is a file that was modified after install, because it may contain
your work. Never clean up a file you cannot prove you created.

**Subprocess safety.** `git` is invoked with an argv array and never a formatted shell
string, and path lists are chunked at 100. A filename with a space in a string-built command
is a different command, and a few hundred paths exceeds the command-line limit with a
confusing error.

### Install profiles

Four, because the honest shapes for one organization's repositories are just-analysis,
the-whole-thing, gating-only, and in-a-band.

| Profile | For |
|---|---|
| `context-only` | A repository that wants `/orchestrator-init` and `/analyze` and nothing else. No pipeline, no memory sync, no hooks. |
| `standard` | The default. Full pipeline, all skills, shared memory, hooks at the `standard` profile. |
| `reviewer` | Review, security and verification only — a repository where the orchestrator gates pull requests but does not write code. |
| `band-member` | `standard` plus registry sync and contract hand-off, for a repository in a cross-repo band. |

A profile is a starting point rather than a cage: `connect-repo.ps1` accepts `-With` and
`-Without`, and the resolved set is recorded in the install state so `repair` reproduces the
intent rather than guessing at it.

---

## 12. File reference

| Path | Owns |
|---|---|
| `hub.config.json` | Organization identity, hub version and repository, plugin install coordinates, state home. The only sanctioned home for an org string. |
| `orchestrator-hub.yml` | The hub marker file and declaration of shape. Read by a new human and by the view plane; not a runtime config. |
| `.claude-plugin/plugin.json` | The plugin manifest and its user-configurable options. Must **not** declare `hooks`. |
| `.claude-plugin/marketplace.json` | Makes this repository a marketplace one command can add. |
| `hooks/hooks.json` | Hook registrations. Auto-loaded by convention. |
| `config/token-budgets.json` | Every ceiling, the priority order, and the derivation block. |
| `config/pipeline-graph.json` | The SDLC DAG, gates, human gates, and checkpoint paths. |
| `config/stack-mappings.json` | Stack detection. |
| `config/tool-registry.json` | The declared tool surface. |
| `config/redaction-patterns.json` | The redaction taxonomy, suppressions and sink polarities. |
| `config/install-profiles.json` | The four profiles and their components. |
| `hooks/runtime/registry.json` | The single source of truth for hook wiring, read by `run.js`, `dispatch.js` and the validator. |
| `hooks/runtime/flags.js` | Whether a given hook runs at all. |
| `hooks/runtime/run.js` / `dispatch.js` | Single-hook and batched entry points. |
| `lib/config.js`, `paths.js`, `state.js`, `redact.js` | Shared JavaScript for the handlers. |
| `scripts/_lib.py` | The inventories (agents, skills, commands, contexts, hooks), the frontmatter parser, the discovery measurement, and the redaction scan. The manifest. |
| `scripts/gen-content.py` | Renders the content plane from `content-src/`. `--check` in CI. |
| `scripts/validate-structure.py` | Twenty checks: manifest, frontmatter, ratchet pins, least privilege, wiring parity, plane separation, org neutrality. |
| `scripts/measure-discovery-budget.py` | The ratchet. |
| `scripts/context-bill.py` | The context bill of materials. |
| `scripts/orchestrator.py` | The install lifecycle. |
| `scripts/pipeline.py` | The DAG scheduler, gates and checkpoints. |
| `scripts/cross-repo.py` | Registry, groups, band and locks. |
| `scripts/memory.py` / `decision.py` | The memory write path and the append-only decision log. |
| `scripts/graph.py` / `grounding.py` | The structural index and the evidence manifest. |
| `scripts/redact.py` / `egress-receipt.py` | The scanner and the ledger. |
| `evals/evals.json` / `touchfiles.json` / `eval-runner.py` | Eighteen cases, their diff selectors, and the harness. |
| `memory/README.md` | Tiers, confidence arithmetic, promotion rule, decay policy. |

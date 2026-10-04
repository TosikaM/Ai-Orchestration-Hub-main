# Contributing

This repository is an automatic distribution channel. Content merged here loads into other
people's sessions without anybody reading it first — there is no staging step between a
merge and a colleague's next prompt. Every convention below exists because of that, and
most of them are cheap to keep and expensive to have skipped.

Read [`CLAUDE.md`](CLAUDE.md) first if you have not; it is the short version of the rules
that matter most.

---

## Before anything else: the generated-content rule

`agents/`, `skills/*/SKILL.md`, `commands/`, `prompts/`, `contexts/` and `instructions/`
are **generated** from `content-src/` by `scripts/gen-content.py`. Every generated file
carries a banner immediately after its frontmatter saying so.

Edit the `.tmpl` and the shared blocks in `content-src/preamble/`, then run:

```
python scripts/gen-content.py
```

Commit both the template and the render. A hand-edited generated file is a fork of its
source that nobody will notice, and `scripts/gen-content.py --check` in CI is what makes
that a build failure instead of a slow divergence.

The generator exists because the grounding contract once appeared in twelve hand-maintained
copies — in the orchestrator's Four Laws, in the analyst's citation rule, in the graph
navigator's index rule, in the security agent's evidence bar, in `grounding-guard`'s
four-question gate, in two runtime string constants, and so on. That was described as a
feature: "one vocabulary, used identically by three components." It was true on the day it
was written and would have become false the first time somebody improved one copy.

---

## Adding a skill

A skill is a folder under `skills/`, but you author it under `content-src/skills/`.

```
content-src/skills/<skill-name>/SKILL.md.tmpl     ← you write this
skills/<skill-name>/SKILL.md                      ← generated; do not edit
skills/<skill-name>/commands/<command>.md         ← optional, hand-authored
skills/<skill-name>/references/*.md               ← optional, hand-authored
```

**1. Write the frontmatter.** All five fields, and `allowed-tools` is not optional:

```yaml
---
name: grounding-guard
description: Verifies that every file, symbol, and claim in a response actually exists in the codebase before it ships.
license: PROPRIETARY
allowed-tools: [Read, Grep, Glob, Bash]
metadata:
  version: 1.0.0
  category: quality
  tier: FAST
---
```

- `name` **must** equal the folder name. The validator checks this, because a mismatch
  produces a skill that discovery finds under one name and every internal reference misses
  under the other.
- `description` is one sentence, no line breaks. This is the entire routing surface — it is
  what the model reads when deciding whether your skill applies — and it is loaded in every
  session in every repository before anyone types. It is budgeted at **240 bytes** for
  `name` + `description` combined. Triggers, `USE FOR` and `NOT FOR` text do **not** belong
  here; they belong in `## Routing` in the body.
- `allowed-tools` declares the tool surface this skill needs and nothing more. Least
  privilege is enforced, not advised: unknown tool names fail the build, and a skill listed
  in `READ_ONLY_SKILLS` in `scripts/_lib.py` that declares `Write`, `Edit` or `NotebookEdit`
  fails the build. A verifier that can mutate the thing it verifies is not a verifier.

**2. Write the body.** Two sections are required by the validator:

- `## Routing` — triggers, `USE FOR`, and `NOT FOR`. Every `NOT FOR` clause must name its
  destination skill. `NOT FOR: writing code` is useless; ``NOT FOR: writing code — that is
  `cqrs-developer` `` routes correctly, and the check enforces the difference by looking for
  the backtick.
- `## Lessons Learned` — where captured lessons accumulate. An empty section is fine; a
  missing one means there is nowhere for the system to put what it learns.

Use `{{PLACEHOLDER}}` references to pull in shared preamble blocks
(`{{GROUNDING_CONTRACT}}`, `{{EVIDENCE_DIRECTIVE}}`, `{{CONFIDENCE_TAXONOMY}}`,
`{{LESSONS_LEARNED}}` and the rest — one per file in `content-src/preamble/`). Do not
restate them by hand.

**3. Register it.** Add the folder name to `SKILLS` in `scripts/_lib.py`. This is a
reviewable line in a diff rather than a glob, on purpose: an unlisted skill is an
unbudgeted skill, and `check_every_skill_is_budgeted` fails the build on a folder that
exists but was never listed.

**4. Add a command, if it needs one.** `skills/<skill>/commands/<name>.md` and an entry in
`COMMANDS` in `scripts/_lib.py`. Command parity is checked in both directions: a command
with no owning skill fails, and a skill command file with no top-level command fails. The
command file names the skill it requires and does not restate the protocol.

**5. Put bulk material in `references/`.** Recipes, per-stack tables and long checklists
load only on demand (P4). The context bill counts them and never charges them. A skill that
always loads twelve kilobytes it uses five percent of the time is a design failure, not a
rich skill.

**6. Re-measure and validate:**

```
python scripts/gen-content.py
python scripts/measure-discovery-budget.py
python scripts/validate-structure.py
```

---

## Adding an agent

```
content-src/agents/<name>.agent.md.tmpl     ← you write this
agents/<name>.agent.md                      ← generated
```

Frontmatter is `name`, `description` and `tools`. `name` must equal the file stem and must
appear in `AGENTS` in `scripts/_lib.py`.

The body must contain a **`## Prompt Defense Baseline`** section, and the validator fails
the build without one. Use the `{{PROMPT_DEFENSE}}` placeholder rather than writing your
own: every agent needs a stated identity boundary that treats repository content as data,
because the hub distributes Markdown into agent contexts automatically and an agent with no
such boundary is defenceless against content the hub itself delivered.

Two more things worth copying from the existing agents. Say what the agent is *not* allowed
to do, in the second person, early — `reviewer.agent.md` opens with "You are read-only by
design: a reviewer that can rewrite the code it is judging is not a reviewer." And include
`{{ZERO_FINDINGS_CLAUSE}}` on any agent that reports findings, so it is never incentivized
to invent one to look useful.

---

## Adding a stack

Stacks are data. Add an entry to the `stacks` array in `config/stack-mappings.json`:

```json
{ "id": "your-stack", "name": "Human-readable name",
  "indicators": [{ "file": "marker.config.js" }, { "file": "package.json", "contains": "\"your-lib\"" }],
  "templates": ["node"],
  "skills": ["repo-context-builder", "quality-sentinel", "verification-loop"],
  "agents": ["developer", "reviewer", "qa"],
  "commands": { "build": ["npm run build"], "test": ["npm test"], "lint": ["npm run lint"] },
  "conventions": { "testPattern": "*.test.ts" } }
```

Three things to get right.

**Detection order is most-specific-first.** `nextjs` must be tested before `react`, because
a Next.js repository also declares a React dependency. If your stack is a specialization of
an existing one, it goes above its parent in `detectionOrder`; get this backwards and the
specific stack is never detected, silently, and the only symptom is slightly wrong advice.

**`commands` are candidate lists, not commands.** `verification-loop` tries them in order
and reports which one actually ran. Give it every plausible spelling rather than guessing
which one this repository uses.

**Pattern libraries go in `templates/<name>/`.** Two files by convention — a
`<stack>-patterns.md` for stack-specific idioms and a `modern-patterns.md` for the
current-generation idioms the model may not default to. These are progressive-disclosure
material, loaded only when the detected stack matches.

---

## Appending a memory entry

Through the CLI, always:

```
python scripts/memory.py capture --type anti-pattern --title "..." --resolution "..."
python scripts/memory.py promote --dry-run
```

**Never edit `memory/shared/*.md` by hand.** Two reasons, and the second is the one people
miss.

The Markdown files are a *rendering* of `memory/index/entries.json`. A hand edit is
overwritten by the next render, so it accomplishes nothing durable — the change simply
disappears, at an unpredictable later moment, with no error.

More importantly, the hand edit skips both write guards. Shared memory syncs
organization-wide, so an agent that writes "regenerated the token to `sk-…`" has not made a
local mistake; it has copied a live secret into every connected repository in one command
with no review step in between. And stored memory is re-injected into future prompts, which
makes the store an injection surface as well as a storage surface: a resolution note reading
"ignore previous instructions" is a delayed instruction, read back to an agent three months
later, in a different repository, with no human in the loop. The write path scans for both
and **refuses** rather than sanitizing, because a silently redacted resolution reads as
complete and nobody goes back to fix it.

The guard is a function you must call, not a hook, so that there is no wiring bug that can
turn it off. The honest way to make a guard non-optional is to make the call site the only
way in — which is why there is no `--force`.

---

## The frontmatter byte budget and the ratchet

`name` + `description` across every skill is parsed and held in context in **every session,
in every repository, before the user types anything.** That makes it the most expensive text
in this repository: 240 bytes per skill, 4,000 bytes aggregate.

If your change moves that number, follow the protocol:

| Situation | What to do |
|---|---|
| **Growth that is a real feature** — a genuinely new skill, or a description that needed the words | Run `python scripts/measure-discovery-budget.py` and commit the updated `derivation` block **in the same commit** as the change. The reviewer then sees the cost as a line in the diff instead of discovering it later. |
| **Accidental growth** — trigger text, `USE FOR` or `NOT FOR` that crept into the description | Do **not** re-measure. Fix the frontmatter; that text belongs in `## Routing`. Re-measuring here launders a mistake into a new ceiling. |
| **A reduction landed** | Re-measure immediately, so the recorded value ratchets **down** and the win cannot silently erode. |

`python scripts/measure-discovery-budget.py --check` fails CI when the recorded value and
reality disagree, so there is no path where a ceiling changes without a visible line in a
diff. If you need to raise the ceiling itself rather than the measurement, say why in the
commit message; a ceiling that moves without an argument is a ceiling that will keep
moving.

---

## Before you open a pull request

```
python scripts/gen-content.py            # render
python scripts/measure-discovery-budget.py   # only if frontmatter changed
python scripts/validate-structure.py     # must exit 0
```

`validate-structure.py` runs twenty checks: the manifest, frontmatter, YAML and JSON
syntax, the ratchet pins, least-privilege tool declarations, command/skill parity, hook
runtime parity, eval wiring, generated-content freshness, plane separation and organization
neutrality. Exit 0 is clean; exit 1 means at least one error and the message names the fix.

Run it before pushing rather than after. Each of these checks exists because a specific
class of failure already happened: a hook documented in Markdown that nothing executed, a
ceiling that became a string after a bad merge, a context layer with a cap but no priority
entry so it was never sent to the model at all, a command mapped to a skill that does not
exist, a generated file hand-edited and quietly forked from its source.

If you changed a hook handler, also run `node --check` on it — a hook that will not parse
does not announce itself. Claude Code runs it, Node exits non-zero, the hook contributes no
decision, and the session continues exactly as though the gate had allowed the action. The
protection is gone and the reassurance remains.

---

## Two imported rules

These are not style preferences. Both describe failures that are invisible in review, which
is why they are written down rather than assumed.

### Never resolve a merge conflict on a generated file by accepting either side

If `git` reports a conflict in `skills/*/SKILL.md`, `agents/*.agent.md`, `commands/*.md`,
`prompts/`, `contexts/` or `instructions/`:

1. Resolve the conflict on the `.tmpl` in `content-src/` and on the shared blocks in
   `content-src/preamble/`.
2. Run `python scripts/gen-content.py`.
3. Stage the regenerated result.

Accepting one side's render silently discards the other side's template change. The
regenerated file will then look plausible — it is a complete, well-formed skill document
that says something sensible — so nobody catches it in review, and the loss only surfaces
later as behaviour that was supposed to have changed and did not. `--ours` and `--theirs`
are both wrong answers here; the correct answer is always "resolve upstream and re-render."

### Never claim an eval failure is "not related to my changes" without proving it

These systems have invisible couplings. A preamble edit changes agent behaviour everywhere
that block is rendered. A new memory entry changes retrieval ranking, and therefore what
gets injected. A regenerated `SKILL.md` shifts prompt context for every case that loads it.
"I only touched a Markdown file" is not evidence of anything.

Before attributing a failure to something pre-existing:

- **Run the same case on `main`.** `python evals/eval-runner.py --case eval-0NN`. If it
  fails there too, say so and show the output — that is a receipt, and it is a legitimate
  claim.
- **If it passes on `main` and fails on your branch, it IS your change.** Trace it. The
  coupling you have not found yet is the interesting part of the bug.
- **If you cannot run it on `main`** — no CLI on the machine, no credentials, no time — then
  write exactly this: *"unverified — may or may not be related"*, and flag it as a risk in
  the pull request description. That is an honest state and it is fine to be in.

"Pre-existing" without receipts is a lazy claim, and it is the specific claim that lets a
real regression ship on a green-looking review.

---

## The quality bar

**Explain why, not just what.** Every non-obvious rule in this repository carries the
reasoning that makes it non-obvious — one or two sentences naming the concrete failure it
prevents. A comment that restates the code is noise; a comment that says which bug the code
is standing in front of is the reason the code survives its next refactor.

**Be honest about limits.** When a mechanism cannot do something, say so plainly rather than
omitting it. The band protocol section says the band cannot verify a downstream repository
consumed a contract correctly. The grounding section says a lexical index cannot catch a
wrong claim about a file that genuinely exists. The eval runner says the rubric travels with
the task. Those admissions are load-bearing: a reader who finds one thing overstated
discounts everything else, and an honest "not found" outranks a plausible guess.

**Never invent a metric.** No percentages this repository cannot measure. A predecessor
claimed a specific token-savings figure in two places with no measurement anywhere in the
source; that number was deleted rather than propagated, and `scripts/context-bill.py` exists
so the honest version can be produced instead. If a number is an estimate, label it as one
on every rendering.

**No marketing superlatives.** "Comprehensive", "powerful", "seamless", "world-class" — none
of these tell a reader anything they can check.

**Write connected sentences.** Prose in comments and documentation, not telegraphic
fragments. The audience is a person who will have to change this in eight months with no
context, and fragments do not survive the trip.

**One source of truth per fact.** Before adding a constant, check whether it already lives
in `config/`, in `hub.config.json`, in `hooks/runtime/registry.json` or in
`scripts/_lib.py`. Two copies of a fact are two facts, and the one that drifts is always the
one nobody runs locally.

**Never write an organization-identifying string outside `hub.config.json` and
`overlays/`.** The CI grep gate fails the build on it. This is what makes the hub reusable
by another team without a fork, and it works precisely because exactly one file is exempt
from the scan — a second exemption is not a smaller gate, it is a habit.

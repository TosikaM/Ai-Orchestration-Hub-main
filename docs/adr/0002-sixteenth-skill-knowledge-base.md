# ADR-0002: A sixteenth skill for requirements, paid for out of measured headroom

- **Status:** Accepted
- **Date:** 2026-09-08
- **Deciders:** Algoworks AI Platform Team
- **Decision log id:** d-0002

## Context

Two standing constraints pull in opposite directions here, and this decision is about
which one gives.

The first is the discovery budget. Every skill's frontmatter `name` and `description` is
parsed and held in context in every session, in every repository, before the user types
anything — the most expensive budget in the system precisely because it is paid
unconditionally. `config/token-budgets.json` caps it at 240 bytes per skill and 4000
bytes in aggregate, and the standing instruction that follows from it is blunt: hold the
discovery budget, adopt patterns rather than catalog them. Fifteen skills that each earn
their line beat twenty-five that do not.

The second is grounding. Every skill in this system is forbidden from asserting a fact
about the codebase without a `file:line` to back it. That rule is enforced twice — by the
citation guard on output and by the fact-forcing gate before an edit, whose reasoning is
recorded at `hooks/runtime/handlers/fact-force.js:32-52`. The insight it rests on is that
asking a model whether it is sure is answered "yes" by construction, while forcing
retrieval is not: an agent cannot produce an importer list without actually searching.

Requirements had no equivalent discipline, and the gap is not hypothetical. An agent
reads a specification, a compliance rule or an interface contract once, early in a
session. Three sessions later it states that requirement from memory, in the same
confident register it would use for a fact it had just verified with a `file:line`, and
nothing in the system can tell the difference — because the fact-forcing gate asks about
files, and a requirement is not a file the agent is editing. The system had a strong
answer for "what does this code do" and no answer at all for "what did the contract
say", which is the question that decides whether the code is right.

That asymmetry is what justifies spending budget rather than economising on it.

## Decision

Add a sixteenth skill, `knowledge-base`, and a tenth agent, `knowledge-curator`, and pay
for them out of measured headroom under the existing discovery ceiling rather than by
raising the ceiling.

## Options considered

### Option A — Add `knowledge-base` and re-measure the ratchet (chosen)

- **How it works:** A dedicated skill for ingesting and querying a requirements corpus,
  with the same citation discipline the code-facing skills already carry: a requirement
  is quoted with its source, or it is not stated. The `knowledge-curator` agent owns
  ingestion and de-duplication, so curation does not leak into the skills that answer
  questions. The skill's frontmatter is written to the existing 240-byte per-skill cap,
  with its triggers and its `USE FOR` / `NOT FOR` routing in the `## Routing` body where
  they cost nothing until the skill is actually invoked. The aggregate ceiling in
  `config/token-budgets.json` does not move; the measured value underneath it does, and
  it is re-measured and committed as part of this change.
- **What it costs:** One permanent, always-on line of discovery context, plus the tenth
  agent's description, plus the maintenance of a corpus that will go stale if nobody
  curates it. A stale requirements store answering with confidence is worse than no
  store, because it launders an out-of-date rule into a cited one.
- **What it forecloses:** The remaining headroom is small enough that this is close to
  the last skill that can be added without either a reduction elsewhere or an explicit,
  argued increase to the ceiling. That is the intended effect, not a side effect: the
  next proposal has to make a harder case than this one did.

### Option B — Fold knowledge queries into `repo-context-builder` (rejected)

- **How it works:** Extend the existing repository-context skill to also ingest and
  answer from the requirements corpus, adding no new discovery line at all.
- **What it costs:** Nothing in discovery bytes, which is exactly what makes it
  tempting. It costs coherence instead: one skill that conflates facts about the code
  with facts about the contract, verified by different means, stale on different
  schedules, and wrong in different ways.
- **Why rejected:** The `NOT FOR` clause becomes unwritable. Every skill in this system
  must state what it is not for and name the skill that handles it instead — the
  validator rejects a `NOT FOR` clause that does not route somewhere, because
  "NOT FOR: writing code" helps nobody while "that is `cqrs-developer`" does. A skill
  that owns both "what does this code do" and "what did the specification require" has
  no boundary left to state, and a skill whose boundary cannot be written is a skill the
  model will invoke for the wrong question. Saving a discovery line by making the
  routing incoherent trades a cost we can measure for one we cannot.

### Option C — Keep the corpus outside the system and paste excerpts by hand (rejected)

- **How it works:** Requirements stay in the document store they already live in.
  Whoever needs one opens it, copies the relevant passage, and pastes it into the
  session.
- **What it costs:** Zero discovery bytes and zero maintenance, at the price of relying
  on a human to notice that a requirement is relevant before the agent has stated it.
- **Why rejected:** This is not a mitigation of the problem; it is a restatement of it.
  The uncited requirement gets stated when nobody thought to paste anything — that is the
  failure mode by definition. A discipline that only operates when someone remembers to
  invoke it is not a discipline, and the whole argument for the fact-forcing gate is that
  forced retrieval works where remembering does not.

## Strongest argument against this decision

Every skill added is a permanent, always-on cost paid by every user in every repository
forever, and "we have headroom" is precisely how a budget erodes — one well-argued skill
at a time, each of which is individually justified and none of which is the one that
broke it.

This proposal is a good one. So was every proposal that ever moved a ceiling. The
argument in the Context section is genuinely strong and that is what should worry the
reader: a weak argument gets rejected, a strong one gets accepted, and after four strong
ones the discovery footprint has doubled and no single decision was wrong. The disciplined
alternative was available and was not taken — find a skill in the current sixteen that has
not earned its line, or tighten three descriptions by twenty bytes each, and add this one
at net zero. That would have been harder, and it is the version of this change that
leaves the budget where it found it.

The counter-argument, honestly stated, is that the uncited-requirement failure is a
grounding failure, and grounding is the thing this system exists to enforce. But that
reasoning would justify the next skill too.

## Consequences

- **Positive:** Requirements acquire the same citation discipline the codebase already
  has. The gap between "what does this code do" (answerable with a `file:line`) and
  "what did the contract say" (previously answerable from memory, with no way to tell)
  closes. The ceiling does not move, so the ratchet stays intact and the next proposal
  faces the same test this one did.
- **Negative:** Sixteen skills of permanent discovery cost instead of fifteen, and less
  room for the seventeenth. The tenth agent's description is a further always-on cost
  that the discovery budget as currently defined **does not measure** — the measurement
  in `scripts/measure-discovery-budget.py` sums skill frontmatter only. Saying so is
  better than implying the agent is free; if agent descriptions become the dominant
  always-on cost, the budget's definition is what needs revisiting, not this decision.
  A curated corpus also needs an owner, and an uncurated one degrades into confidently
  cited staleness.
- **The headroom figure, stated honestly:** With 16 skills and a 240-byte per-skill cap,
  the arithmetic upper bound on the aggregate is 3,840 bytes against a 4,000-byte
  ceiling — 160 bytes of headroom in the worst case where every skill sits exactly at its
  cap. That is arithmetic, not a measurement. The actual figure is whatever
  `measure_discovery` returns, and it is currently **unknown**: `measuredValue` and
  `measuredAt` are `null` in `config/token-budgets.json:12-13`, because the measurement
  has not been run.
- **Why that is not merely an omission:** `check_budget_provenance` in
  `scripts/validate-structure.py` treats a null or non-integer `measuredValue` as a
  disabled ceiling and fails, and `python scripts/measure-discovery-budget.py --check`
  runs in CI as its own step. The build is therefore red until the measurement is taken.
  That is the correct behaviour and it is the reason this ADR can be Accepted with the
  number missing: nothing will merge on the strength of an unverified claim.
- **Reversal cost:** An estimate, not a measurement. Low, and deliberately so. Removing
  the skill is deleting `skills/knowledge-base/`, its entry in `SKILLS` in
  `scripts/_lib.py`, its command files and its eval cases, then re-running the
  measurement so the ceiling ratchets back **down** and the reclaimed bytes are locked
  in rather than quietly re-spent. An hour or two of work, no consumer-repository impact,
  and no data loss — the ingested corpus is a store, not a schema. The genuinely
  irreversible part is cultural: once the budget has been spent on a persuasive case, the
  next persuasive case has a precedent to point at.

## Follow-ups

- **Run the measurement and commit the value in the same change as the skill.** This
  cannot be done on the machine that authored these files — Python is not installed
  there, so nothing in `scripts/` has been executed. The first person with a working
  Python 3.12 environment runs:

  ```
  python scripts/measure-discovery-budget.py
  ```

  and commits the resulting `measuredValue`, `measuredAt`, `dominantSkill` and
  `headroomPercent` into `config/token-budgets.json`. The `ratchetProtocol` recorded in
  that file is the rule to follow: growth that is a real feature updates the record in
  the same commit so the increase is a visible line in the diff; growth that is trigger
  text which belongs in `## Routing` is fixed in the frontmatter instead of in the
  ceiling. Owner: the first engineer to run CI green.
- **If the measured aggregate exceeds 4,000 bytes, do not raise the ceiling in this
  change.** Reduce the descriptions until it fits, or reopen this ADR. A ceiling raised
  in the same commit as the thing that breached it is not a ceiling.
- **Assign a curator for the requirements corpus.** An ingestion pipeline with no owner
  produces a store that is confidently wrong within a quarter, which is worse than the
  gap it was built to close. Owner: AI Platform Team.
- **Record this decision in the decision log**, after ADR-0001's — ids are assigned by
  insertion order, so logging this one first would make it `d-0001` and the numbers in
  these two files would no longer match the log:

  ```
  python scripts/decision.py log \
    --decision "Add a sixteenth skill, knowledge-base, and a tenth agent, knowledge-curator, funded from measured discovery headroom rather than by raising the ceiling" \
    --rationale "Requirements had no citation discipline, so an agent states a remembered requirement with the same confidence as a verified fact; the discovery ceiling stays fixed and the measurement is re-taken in the same change" \
    --alternatives "Fold into repo-context-builder (rejected: the NOT FOR boundary becomes unwritable); keep the corpus outside the system and paste by hand (rejected: that is the uncited-requirement problem restated)" \
    --adr docs/adr/0002-sixteenth-skill-knowledge-base.md
  ```

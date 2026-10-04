# The CNP knowledge base, and whether the orchestrator earned its keep

**Date:** 2026-09-10
**Scope:** the LINQ CNP corpus ingested into `knowledge/`, the synthesis in `context/`,
and an honest comparison against the alternative of handing the same documents straight
to Claude.

Every number in this document is either measured in the session it describes or labelled
as an estimate. Where the orchestrator did not help, that is stated rather than omitted.

---

## Part 1 — What the project is, in business terms

LINQ sells administration software to state agencies that run USDA Child Nutrition
Programs — school meals, daycare meals, summer meals. Two legacy product lines serve 28
states today: **CTS** (22+ states, cloud) and **DIS** (6 states, WinForms desktop). The
project replaces both with one codebase serving all 28.

The business problem underneath it is **the cost of variation**. Every state wants its
own rules, and satisfying that today means a developer and a deployment. The bet is a
platform where states configure instead — with a hard ceiling: *configurable up to the
edge of federal law, and everything federal law mandates is in code and structurally
locked.*

Engineering deliberately refuses the "BPM + ERP" framing used with executives, because
*"an engineer building a true BPM engine to spec would produce a system with no federal
guardrails"* (`context/07-decisions.md#d1-naming`).

### Why the compliance obsession is not over-engineering

A Sponsor — a school district, daycare centre, camp operator — submits an annual
application. **Approval is what unlocks their ability to claim federal reimbursement for
meals served.** An approval is therefore a gate on federal money, and FNS auditors must
be able to reconstruct any past decision years later.

That single fact generates almost every unusual requirement in the corpus: the immutable
`ClaimLaws` snapshot, the append-only audit trail, the segregation-of-duties rule on NDL
clearance, and the refusal to allow any edit path on a frozen record.

### Phase 1 is a sales proof, not a product

16 weeks (14 build + 2 freeze), one state's SNP application-to-approval flow, demonstrated
live. 51 features, 2,264 hours. Two of the twelve demo-readiness criteria carry the
*commercial* argument rather than a technical one:

- **The speed demo** — an admin changes a live setting and it is visible in the workflow
  in under 5 minutes, against a documented story of how long the same change takes in the
  legacy product.
- **The guardrail demo** — a federal value cannot be changed through *any* path, including
  a direct SQL write, and every blocked attempt is auditable.

That is the whole pitch rendered as software: **fast where you are allowed, immovable
where you are not.**

### The three ideas everything hangs off

1. **`IsFederal`** — a structural lock at six surfaces with no override mechanism,
   enforced in three non-equivalent layers: UI suppression (usability, *not* the control),
   the API guardrail (bypassed by direct SQL or a migration), and database triggers (fire
   for every write regardless of source). Blocked attempts are written to `AuditLogs` in
   an **autonomous transaction**, so the rollback that rejects the write does not erase
   the evidence it was attempted.
2. **Schema-per-tenant, no `TenantId` column anywhere.** The schema name *is* the tenant.
   The rejected alternative fails *silently* the moment one `WHERE` clause is missing.
3. **`ClaimLaws`** — exactly one immutable snapshot per approval, reflecting the rules in
   force at the literal moment of approval, with no edit path at all.

---

## Part 2 — What the corpus actually contains

Measured on 2026-09-09:

| Layer | Size | Count |
|---|---|---|
| `knowledge/inbox/` (source, incl. PDF/PNG binary) | 60,026,550 B | 46 documents |
| `knowledge/extracted/` (mechanical text) | 583,548 B | 45 documents |
| `knowledge/distilled/` (curated by topic) | 285,190 B | 15 topics |
| `context/` (synthesis) | 117,657 B | 8 files + provenance |
| Index | — | 258 anchors, **45 unresolved conflicts** |

The eager digest is capped at **1,000 characters** (`config/token-budgets.json`,
`eager.layers.knowledgeDigest`). Everything else is retrieved on demand.

**Read the compression honestly.** The 60 MB figure is mostly PDF and PNG binary and is
not a fair denominator. The real ratios are: extracted → distilled ≈ **2:1**, and
distilled → what loads before you type ≈ **285:1**. The second number is the one that
matters, and it is a *retrieval* property, not a summarisation one — the 285 KB is still
there, addressable by anchor.

---

## Part 3 — What is missing, and what is contradictory

This is the part a summary would have smoothed over, and it is the most valuable content
in the corpus.

### 45 conflicts, none resolved

The client stated the rule twice, in two independent documents: *"where this document and
a customer design document conflict, the design document wins. Flag conflicts; don't
silently resolve them."* All 45 are recorded with both sides quoted and cited.

The sharpest ones:

| # | Question | Why it blocks |
|---|---|---|
| 1 | Does `ClaimLaws` store dollar rates, or only the eligibility tier? | Three design docs say no; the reference C# says yes; the newest doc makes it an **acceptance criterion**. Determines a table schema and a service signature. |
| 2 | Which identity provider? | Harmony Auth (conditional), Cognito (fallback), Keycloak (newest doc). A Week-0 blocker affecting ECS and Secrets Manager paths. |
| 3b | Must Phase 1 provision a **second state**? | Three of ten foundation acceptance criteria require it; the Prototype document says *"One state only."* Real, unestimated scope. |
| 6 | Does the lifecycle include `Returned`, and can an application be `Denied` at all? | The newest architecture states the machine with **no terminal deny state**. A prototype that cannot deny is a materially different demo. |
| 7 | `Declined` or `Denied`? | A literal the UI, the API contract and seed data all key off. Trivial now, expensive after the Sprint-4 contract freeze. |

### Seven documents referenced as inputs but never supplied

Including `CNP_Phase1_High-Level_Test_Plan.docx` (defines TS-01–TS-13) and
`CNP_Phase1_Test_Execution_Sprint_Plan.xlsx` (83 scenarios, SC-101–SC-1303). **Every FRD
cross-references those suites.** The practical consequence: QA has no scenario catalog and
RF→test traceability cannot be rebuilt from this handover.

### Commitments in the customer deck that engineering has not designed

- The deck promises **S3 Object Lock (WORM)** and a *"tamper-evident"* audit trail. No
  engineering document specifies Object Lock, WORM, or any tamper-*evidence* mechanism.
  Append-only-by-absence-of-a-DELETE-path prevents casual modification; it does not prove
  to an auditor that nothing was modified.
- The deck describes **per-object rights**, which is the ACL model ADR-006 explicitly
  rejected in favour of nine roles.
- The deck **describes the database trigger incorrectly** — an engineer building to the
  deck would write the wrong trigger.

### Gates that block Week 1 and are not started

The synthetic test data pipeline and offshore DLP controls are both stated prerequisites
for the offshore team receiving *any* environment access, and the plan has them starting
in Week 1. The DR plan is annotated in its own source as *"This is completely fabricated.
Need to discuss with Ed."*

### One inconsistency inside our own synthesis

`context/00-overview.md:142` and `context/07-decisions.md:201` both say "39 conflicts",
while `context/06-open-questions.md:13` says 45. The newest client document added six and
those two lines were not updated. Recorded here rather than quietly fixed.

---

## Part 4 — Orchestrator vs. handing the documents to Claude directly

### Setting up a fair comparison

The weak version of this argument is "the documents don't fit in context." **That is no
longer true and should not be claimed.** The extracted text is 583,548 B ≈ 146k tokens at
4 chars/token. A 1M-context model holds that comfortably. Any honest case for the
orchestrator has to survive that fact.

So the comparison below is against a genuinely strong baseline: *paste all 46 documents
into a 1M-context session and ask good questions.*

### Where the orchestrator genuinely wins

**1. Provenance survives the answer.**
Every claim in `context/` carries a `<!-- from: knowledge/distilled/<topic>.md#<anchor> -->`
comment, and `python scripts/project-context.py check` **fails the build** on a claim
without one. In the code produced this session there are **58 citation lines** across
1,626 lines of source, each resolving to a distilled anchor which resolves to a page or
slide in a client document.

A raw-context session produces correct answers with no durable trail. Three weeks later
nobody can tell which sentence in which PDF justified a schema decision. This is the
single largest real difference, and it is about *auditability*, not comprehension.

**2. Contradictions are preserved rather than resolved.**
This is the finding I would most expect a raw session to get wrong, because a helpful
assistant reconciling three sources naturally picks the most plausible one. The corpus
records 45 conflicts with both sides quoted and **none resolved**, because the client
asked for exactly that. A resolved contradiction is indistinguishable from a decision to
the next reader.

Concretely: asked "does `ClaimLaws` store rates?", the corpus answers *"three documents
say no, the reference implementation says yes, the newest makes it an acceptance
criterion, and this is unresolved."* That answer is more useful than either yes or no,
and it is not the answer a summarising pass produces.

**3. It persists across sessions and people.**
The corpus is files on disk. A raw-context session's understanding dies with the
conversation, and the next engineer re-pastes 46 documents and re-derives — possibly
differently.

**4. The hooks own the action stream, not the generation stream.**
A `PreToolUse` hook returning `permissionDecision: "deny"` can stop a write. In this
session the destructive gate blocked an `rm -rf`-shaped command and demanded an
enumeration of what it deleted plus a rollback line, before allowing it. No amount of
prompting achieves that, because prompting shapes what the model *says*, not what the
harness *permits*.

**5. Screen analysis that a script cannot do.**
The extractor writes an honest stub for every image, because a script cannot read a
screen. All six mockups were opened and described. That pass surfaced the site-application
scope question, the per-site eligibility modelling error, and the missing empty states —
**none of which appear in the paired HTML**. A raw pass over the HTML would have missed
all three.

### Where the orchestrator lost, or cost more than it returned

**1. The fact-forcing gate fired 23 times in one session and blocked real work.**
`pre:edit-write:fact-force` demands *"which entry in the file manifest authorizes this
path"*. Its manifest is `scripts/_lib.py` **in the hub repo**. A greenfield project has no
such manifest, so every new source file is unauthorizable by construction. Roughly one
write in two was denied and had to be retried verbatim. On a ~20-file feature that is a
material tax paid for no safety benefit, in the exact scenario the tool is being sold for
— using the orchestrator to build a new project. **This is a bug, not a tuning problem.**

**2. The knowledge base does not travel with the plugin.**
`scripts/ingest-knowledge.py:54-72` resolves the knowledge root to the *workspace*, never
the plugin. Installing the plugin copies `knowledge/` into
`~/.claude/plugins/cache/...` (111 files), where the query tooling will never read it.
Moving to a new project silently yields an empty corpus unless you copy `knowledge/` and
`context/` in by hand. The design decision is right — writing client documents into an
org-wide plugin is a confidentiality problem — but nothing warns you.

**3. Token cost is real, small, and paid unconditionally.**
Measured (estimate at 4 chars/token, from `scripts/context-bill.py`):

| Item | Cost |
|---|---|
| 17 skill descriptions | 2,031 B |
| 10 agent descriptions | 1,963 B |
| 28 command descriptions | 2,136 B |
| **Always-on total** | **6,130 B ≈ 1,533 t** |
| Worst single eager invocation | 2,162 t |
| On-demand (`references/`, not charged unless asked) | 21,574 B |
| Shared memory | 16,053 B |

Discovery footprint sits at **2,031 B against a 4,000 B ceiling (50.8%)**. So the
orchestrator costs roughly 1,500 tokens before you type, in every repo, every session.
That is cheap relative to a 1M window — but it is not free, and it buys routing, not
understanding.

**4. Eval coverage is incomplete, and I did not run the suite.**
`validate-structure.py` reports **12 of 28 commands have no eval coverage**:
`orchestrator-init`, `plan`, `pipeline`, `qa`, `verify`, `release`, `document`, `loop`,
`mcp-compose`, `git`, `mode`, `doctor`. I did not execute `evals/eval-runner.py` in this
session, so **nothing here is an eval-backed claim** — I am reporting structure checks,
not behavioural test results.

**5. Memory is empty and one candidate is malformed.**
`python scripts/memory.py digest` returns *"No memory entries at or above confidence
0.7."* Shared memory still holds ship-time scaffolding. The single entry in
`memory/sessions/learning-candidates.jsonl` has `id: None`, `type: None`, `repos: None`,
a truncated title, and a **pasted session transcript in its `resolution` field** — which
is precisely the failure the skill warns about ("a lesson written mid-task is usually a
fact about that task"). The two-tier promotion machinery is therefore unexercised.

### The honest verdict

| Dimension | Orchestrator | Raw 1M-context Claude |
|---|---|---|
| Requirement comprehension | Comparable | Comparable |
| Citation / auditability | **Strong win** — 58 cited lines, enforced by `project-context.py check` | No durable trail |
| Contradiction handling | **Strong win** — 45 preserved, by rule | Likely to reconcile silently |
| Cross-session persistence | **Win** — files on disk | Dies with the conversation |
| Action-level enforcement | **Win** — hooks can deny | Not possible by prompting |
| Screen/image understanding | Win (stub → human pass, tracked) | Possible, but untracked |
| Token cost before you type | ~1,533 t | 0 |
| Friction on greenfield work | **Loss** — 23 denials | None |
| Setup cost | **Loss** — ingest, curate, copy corpus | Paste and go |
| Eval-backed confidence | Not demonstrated this session | N/A |

**Summary judgement.** On *understanding the requirements*, a 1M-context session with the
same documents would have done comparably well. The orchestrator's defensible advantage is
not comprehension — it is that its output is **citable, contradiction-preserving,
reproducible across sessions, and enforceable at the action layer**. For a project where
an FNS auditor may ask *"what justified this schema decision"* two years from now, those
four properties are the product. For a one-off question about a spec, they are overhead.

The gate friction is the clearest thing to fix, and fixing it is small: treat "no manifest
in this repo" as *not applicable* rather than *denied*.

---

## Deliberately not covered here

- **Eval results.** `evals/eval-runner.py` was not run; it drives the real `claude` CLI and
  spends tokens. No claim in this document is eval-backed.
- **A cost comparison in currency.** I have token estimates, not billing data.
- **A controlled A/B.** The raw-Claude baseline is reasoned about, not executed. I did not
  run the same questions through a no-orchestrator session, so the comparison rows for
  comprehension are argued, not measured. Treat them as 🟡 inferred.
- **`hooks/runtime/registry.json` internals**, which I did not open this session.

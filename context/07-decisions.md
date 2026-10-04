<!-- PROJECT CONTEXT — synthesised, not a source document.

     Every factual claim here needs a provenance comment naming where it came from:
         <!-- from: knowledge/distilled/<topic>.md#<anchor> -->
     `python scripts/project-context.py check` fails on a claim without one.

     If a statement has no source, it is an ASSUMPTION. Move it to 06-open-questions.md
     with the assumption stated, rather than leaving it here where the next reader will
     take it for a requirement. -->

# Decisions

Decisions **the client has already taken**, with the alternatives they rejected and why.

These are recorded because a rejected alternative is the most perishable part of a design: six
months in, someone proposes the thing that was already considered and discarded, and nobody can
remember the reason. Every entry below names what was rejected.

## Architecture {#architecture}

### D1 — Name it a configurable compliance platform, not BPM + ERP {#d1-naming}

**Decision:** engineering documentation says *"configurable federal nutrition compliance
platform."* Executive and nTIG communications may keep "BPM + ERP" where audience familiarity
requires it. No single document serves both audiences.

**Rejected:** keeping BPM + ERP everywhere (*"an engineer building a true BPM engine to spec
would produce a system with no federal guardrails"*); removing it everywhere (loses real
executive-alignment value); adding a disclaimer (*"disclaimers are not read"*); "Rules Engine +
Financial System" (accurate but incomplete, and carries its own baggage).
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#naming -->

### D2 — `IsFederal` is a structural block, not a warning {#d2-isfederal}

**Decision:** a hard code-level lock at six surfaces, with no override mechanism and a stored
federal citation.

**Rejected:** a warning UI with acknowledgment (*"the user dismisses the warning; the
misconfiguration still occurs"*); an approval workflow for federal overrides (*"introduces the
risk that a reviewer approves an incorrect override in good faith"*); audit-only with no block
(*"detects the problem after incorrect reimbursements have already been submitted to FNS"*).

**Rationale:** a hard block is *"the only control that survives staff turnover, onboarding
errors, and edge cases where an administrator believes they are making a legitimate change."*

**Accepted cost:** an annual FNS rate update that changes a locked value **requires a platform
deployment** — it cannot be config-updated.
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#rationale -->
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#consequences -->

### D3 — Schema-per-tenant, no TenantId column {#d3-tenancy}

**Decision:** each state gets its own schema; the schema name is the tenant boundary. The
application selects the schema from the authenticated JWT, never from user input.

**Rejected:** shared schema with a TenantId (*"one missing WHERE clause exposes every state's
data — the failure mode is silent and catastrophic"*; RLS policies are hard to audit); separate
RDS cluster per state (cost-prohibitive at 28 states, 28 independent migration runs, connection
pool overhead).

**Accepted cost:** a single cluster failure affects all states simultaneously, and a DBA
connected to the wrong schema sees the wrong state's data with no warning.
<!-- from: knowledge/distilled/05-data-architecture.md#tenant-boundary -->

### D4 — Append-only audit tables, not event sourcing {#d4-audit}

**Decision:** three append-only tables — `AuditLogs`, `EntitySnapshots` (JSONB),
`FieldChangeLog` — satisfying all five stated audit requirements. All writes through
`IAuditService`.

**Rejected:** event sourcing (*"substantial infrastructure cost and complexity for no additional
audit coverage"* — event store, projection rebuilding, eventual consistency, schema evolution
discipline); database triggers as the mechanism (*"untestable, difficult to maintain, not
portable across schema changes"*).

**Note:** `FormSnapshot` (PDF to S3) is retained as the human-readable legal record.
`EntitySnapshots` is the machine-queryable companion. **Both are required; neither replaces the
other.**
<!-- from: knowledge/distilled/07-audit-and-immutability.md#decision -->
<!-- from: knowledge/distilled/07-audit-and-immutability.md#formsnapshot -->

### D5 — Named hooks, not an expression language {#d5-hooks}

**Decision:** conditions and actions are named identifiers resolved to compiled C# at runtime.

**Rejected:** an expression language — NCalc, MVEL or a custom DSL — which *"allows federal math
to leak into configuration; bypasses code review; untestable in isolation"*; stored-procedure
references (tight coupling to a specific database).

**Accepted cost:** adding a hook requires a deployment. This asymmetry is intentional —
*"configuration is fast; extending the hook library requires review."*
<!-- from: knowledge/distilled/02-workflow-engine.md#named-hooks -->

### D6 — RBAC catalog, not the CnpObjects ACL {#d6-rbac}

**Decision:** ~180 permission entries organised by domain, nine system roles, per-state variation
through `TenantRoleOverrides`, sponsor scoping through a single `ScopeType` column.

**Rejected:** retaining `CnpObjects` (5,082 rows, unmaintainable, *"FNS auditors cannot
interpret it independently"*); ABAC (*"more expressive than needed; runtime policy evaluation is
slower and harder to audit; overkill for nine roles"*).

**Migration is phased:** SECURITY first, then CONFIGURATION, then program domains. Full
migration is not required before Phase 1 launch; `CnpObjects` can coexist. Parallel shadow-mode
validation runs for one school-year cycle before cutover.
<!-- from: knowledge/distilled/04-identity-and-rights.md#rbac-decision -->
<!-- from: knowledge/distilled/04-identity-and-rights.md#acl-migration -->

### D7 — Three-layer configuration hierarchy {#d7-config}

**Decision:** platform default → program default → tenant override, most specific wins, all keys
typed, bounded and effective-dated, resolved only through `ICnpConfigService`.

**Rejected:** `appsettings.json` / environment variables (a deployment per change, and
state-specific values need per-state deployments); a single flat config table with a TenantId
(no resolution hierarchy, no program grouping, no bounds validation).
<!-- from: knowledge/distilled/03-configuration-model.md#hierarchy -->

### D8 — CnpDefaults and LaunchDarkly are separate systems {#d8-config-vs-flags}

**Decision:** ~47 LaunchDarkly flags answer *"does this module exist for this tenant?"*; ~3,000
CnpDefaults answer *"what value does this feature use?"* They must not be conflated.

**Rationale:** *"Whether the late claim cutoff is 60 days or 90 days is not a feature flag
question. Both states have late claim logic, they just use different thresholds. Putting
thresholds in LaunchDarkly would bloat flag management and mix two distinct concerns in one
tool."*
<!-- from: knowledge/distilled/03-configuration-model.md#three-systems -->

### D9 — The Workflow Engine / Rules Engine boundary {#d9-engine-boundary}

**Decision:** the state machine governs transition eligibility and atomic side effects
(synchronous, transactional, can block). The Rules Engine governs operational consequences after
a transition commits (asynchronous, via Hangfire, **cannot block or roll back**).

**The test, in order:** must it prevent a transition → condition hook. Must it run in the same
transaction → action hook. Does it fire after and cannot roll back → Rules Engine.

*"Synchronous/transactional vs. asynchronous/post-commit is the sharpest line between the two
systems. There are no exceptions."* Enforced in code review.
<!-- from: knowledge/distilled/02-workflow-engine.md#rules-engine-boundary -->

### D10 — Approved query templates, not text-to-SQL {#d10-nlp}

**Decision:** the LLM maps a question to a template ID and extracts parameters; `TenantCode` is
injected from the session, never the question.

**Rejected:** arbitrary text-to-SQL (*"cannot reliably prevent cross-state data access; SQL
injection equivalent via natural language; no audit trail of what queries are possible"*);
pre-built reports only (higher support burden, slower iteration).
<!-- from: knowledge/distilled/05-data-architecture.md#nlp-analytics -->

### D11 — DIS and CTS share one platform from the start {#d11-unification}

**Decision:** one codebase for all 28 states. DIS-specific DC feed collection is contained behind
`IDcFeedAdapter`. DIS migration is a parallel track, not a Phase N+1 afterthought.

**Rejected:** CTS-first with DIS later (*"perpetuates two codebases"*, and DIS states watching
the October prototype *"have no reason to stay"* if excluded); a separate DIS platform (doubles
infrastructure, compliance maintenance and federal-math testing surface).

**Known open item:** MO/DHSS is a split-state case requiring design before migration.
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#product -->

### D12 — Modular monolith, not microservices {#d12-monolith}

**Decision:** a single ECS Fargate container, ASP.NET Core, with every domain isolated by
namespace and database schema so services can be extracted later on evidence.

**Rationale:** *"Boundaries are a hypothesis."* In a monolith a wrong boundary is a namespace
rename; in microservices it is a new API contract, a data migration and distributed transaction
complexity. Claims, Accounting, Compliance and Eligibility are named as the likeliest first
extractions.
<!-- from: knowledge/distilled/09-infrastructure-and-environments.md#monolith -->

### D13 — Fiscal actions live in Compliance, not Accounting {#d13-fiscal-actions}

**Decision:** the *calculation* of what is owed is an enforcement function tied to the review
record; the *collection* is a financial instrument in Accounting, which receives only the final
assessed amount.

**Rationale:** the alternative creates a circular dependency — Accounting would need to read
review findings from Compliance to generate fiscal actions.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#fiscal-action-domain -->

### D14 — PDF strategy split by complexity {#d14-pdf}

**Decision:** print CSS for the 90% case with zero infrastructure; QuestPDF server-side for
complex paginated reports; automated status-change snapshots via SQS to S3. `IPdfRenderService`
abstracts both and chooses at render time.

**Rejected:** EvoPdf, the legacy commercial library, is not carried forward.
<!-- from: knowledge/distilled/09-infrastructure-and-environments.md#pdf -->

## Decisions taken about this ingestion {#ingestion-decisions}

Ours, not the client's — recorded here so they are reviewable.

### D15 — Contradictions are recorded, never resolved {#d15-contradictions}

39 conflicts were found and every one is preserved with both sides quoted and cited, rather than
settled by picking the more plausible option.

**Why:** the client states the rule twice in two independent documents — *"where this document
and a customer design document conflict, the design document wins. Flag conflicts; don't
silently resolve them."* A resolved contradiction looks like a decision to the next reader and
is indistinguishable from one; an unresolved one keeps asking the question.
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#precedence -->

### D16 — Distilled by topic, not by document {#d16-by-topic}

The 44 source documents became 14 topic files. Mirroring the filing cabinet would have
reproduced the filing cabinet's retrieval problem — and, more importantly, **the contradictions
are only visible across documents.** "Does ClaimLaws store rates?" cannot be asked of any single
file.

### D17 — Screen stubs were replaced by looking at the screens {#d17-screens}

The extractor writes an honest stub for every image, because a script cannot read a screen. All
six were opened and described with fields, actions, states, navigation and open questions. That
pass is what surfaced the site-application scope question, the per-site eligibility modelling
error, and the missing empty states — none of which are in the HTML.

### D18 — The eager knowledge digest lists documents, not topics {#d18-digest}

`scripts/ingest-knowledge.py` measured the eager digest as a flat list of every anchor. On this
corpus that produced 21,553 B against a 1,000 B cap — larger than the *entire* 18,000-char eager
allocation.

Neither escape was right: consolidating anchors coarsens every citation, and provenance is the
point of this corpus; raising the cap spends the eager budget on a table of contents before the
user types.

**The digest was measuring the wrong thing.** What must load eagerly is enough to know *which
document* answers a question; anchors are retrieved on demand by `search` and `show`. That is
the progressive-disclosure rule this repository already applies to `skills/*/references/`.
Growth is now bounded by document count rather than anchor count: **776 B against the unchanged
1,000 B cap, with 236 anchors still individually citable.**

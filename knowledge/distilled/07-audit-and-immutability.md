# Audit and immutability

## Why this is its own business function {#why-standalone}

Audit is the connective tissue underneath every other function — submissions, review
decisions, screenings, config changes and rate freezes all feed it. It exists as a business
function in its own right because **the guarantee it provides (completeness and permanence)
has to be true system-wide, not reinvented per feature.**
<!-- source: 07_FRD_Audit_Trail.md#section-1 -->

## Append-only tables, not event sourcing {#decision}

The requirements specification originally called for event sourcing. On review, the five
stated audit requirements were: who changed what and when; point-in-time reconstruction of any
record; application state at approval; claim state at payment; form content at submission.

Event sourcing was **rejected** — it requires an event store, projection rebuilding, eventual
consistency handling and schema-evolution discipline, which is substantial infrastructure cost
for no additional audit coverage beyond what append-only tables provide. Database triggers as
the mechanism were also rejected as untestable, hard to maintain and not portable across
schema changes.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-3 -->

*"Append-only means rows are never updated or deleted. Audit integrity is structural, not
enforced by application logic."*
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-3 -->

## The three tables {#tables}

| Table | Captures | Format | Answers |
|---|---|---|---|
| `AuditLogs` | Every user action and system event — a lightweight record of who touched what and when | Rows | *"Show all actions on ClaimId 9944 in the last 30 days"* |
| `EntitySnapshots` | Full structured snapshot of a record's key fields at each status transition | JSONB | *"What was the enrollment count on this application at the time of approval?"* |
| `FieldChangeLog` | Every individual field edit, including intra-status changes between snapshots | Text rows | *"Show every change to SponsorId 1247's address in the last year, including who made each change"* |
<!-- source: CSN-Data-140826-132933.md#page-42 -->
<!-- source: CSN-Data-140826-132933.md#page-43 -->

Columns worth knowing:

- `AuditLogs`: `AuditId`, `TenantCode`, `EntityType`, `EntityId`, `ChangeType`, `ChangedBy`,
  `ChangeDate`, `SessionId`
- `EntitySnapshots`: `SnapshotId`, `TenantCode`, `EntityType`, `EntityId`, `StatusCode`,
  `SnapshotDate`, `DataJson` (JSONB, queryable via SQL JSONB operators), `TriggeredBy`
- `FieldChangeLog`: `ChangeId`, `TenantCode`, `EntityType`, `EntityId`, `FieldName`,
  `OldValue`, `NewValue`, `ChangedBy`, `ChangedAt`, `ChangeSource` (`UI` | `API` | `System`)
<!-- source: CSN-Data-140826-132933.md#page-42 -->
<!-- source: CSN-Data-140826-132933.md#page-43 -->
<!-- source: CSN-Data-140826-132933.md#page-44 -->

All three live in `cnp_ops` (per-state data) and are append-only.
<!-- source: CSN-Data-140826-132933.md#page-44 -->
<!-- source: CSN-Data-140826-132933.md#page-45 -->

### Why all three are needed {#why-three}

`EntitySnapshots` alone would miss intra-status edits: if a user edits a sponsor's address
three times before submitting, `EntitySnapshots` shows only the final state at submission,
while `FieldChangeLog` shows all three. Together they give 100% coverage of data changes.
<!-- source: CSN-Data-140826-132933.md#page-45 -->

## `FormSnapshot` and `EntitySnapshots` are both required {#formsnapshot}

Triggered by the same event — a status change — but serving different audiences:

- **`FormSnapshot`** renders a PDF to S3. It is the **human-readable legal record**, used by an
  auditor opening a case file.
- **`EntitySnapshots`** stores JSONB in the database. It is the **machine-queryable
  companion**, used by systems generating compliance summary reports.

Neither replaces the other.
<!-- source: CSN-Data-140826-132933.md#page-41 -->
<!-- source: CSN-Data-140826-132933.md#page-42 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-4 -->

## The completeness requirements {#completeness}

- **Complete capture.** Every action anywhere that changes something meaningful produces a
  record. There is **no category of consequential action that is silently excluded.**
- **Each record answers who, when, what, and the before/after detail** — the affected data both
  immediately before and immediately after.
- **Genuinely append-only.** Once written, a record cannot be edited or deleted by anyone,
  through any interface, including the most privileged administrative access. Correcting a
  mistake elsewhere produces a *new* record.
- **A human-readable timeline view** — an application's complete history as a single,
  plain-language, chronological timeline, not raw technical log entries requiring
  interpretation.
- **Failed and blocked actions are captured too.** A validation failure, a permission denial or
  a compliance block still produces a record documenting the attempt and why it did not
  succeed.
<!-- source: 07_FRD_Audit_Trail.md#section-3 -->

Three business rules:

- A record's before/after content reflects the actual affected data at that moment — **it is
  not reconstructed or inferred after the fact.**
- Viewing the audit trail requires specific authorization; it is not open to every logged-in
  user by default.
- The completeness guarantee applies without exception to every other business function —
  **none of them are permitted to have an audit gap.**
<!-- source: 07_FRD_Audit_Trail.md#section-4 -->

## The one sanctioned write path {#iauditservice}

All audit writes go through `IAuditService`. **No direct table writes from application code.**
Schema changes to audit tables **add columns only** — never modify or drop existing ones, no
renames, no type changes.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-4 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-3 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-4 -->

## Retention and growth {#retention}

All three tables are **permanent — never deleted** in normal operation, and will grow
unboundedly.

- **Partition by month from initial provisioning.** Retrofitting partitioning on a large table
  is painful.
- Minimum index: `(EntityType, EntityId, CreatedAt)`.
- GIN index on `EntitySnapshots.DataJson` if support or audit queries against snapshot content
  are anticipated.
- `FieldChangeLog` is the high-volume one; consider a more aggressive archiving policy than
  `EntitySnapshots`.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-4 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-16 -->

Deletion of audit records requires a separate privileged data-retention process **outside
normal application code**, triggered only for regulatory compliance (e.g. a GDPR deletion
request for a specific individual).
<!-- source: CSN-Data-140826-132933.md#page-45 -->

## Guardrail violations are audited even when the write is rolled back {#autonomous-tx}

The `log_federal_guardrail_violation()` helper called inside the PostgreSQL triggers writes to
`AuditLogs` **in an autonomous transaction**, so the rollback of the rejected write does not
erase the audit record. Every blocked attempt — regardless of source — produces an `AuditLogs`
row with `EntityType = 'FederalGuardrailViolation'`.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-8 -->

The same pattern protects the PS override justification: written to `AuditLogs` in an
autonomous transaction so it survives a rollback of the override write itself.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-19 -->

## Corrective action is an append-only dialogue {#corrective-action}

`ReviewCorrectiveActionMasters` links to a finding; `ReviewCorrectiveActionDetails` records
each back-and-forth entry between reviewer and sponsor. **Neither party can edit prior entries
— only append.** This is the record of remediation.
<!-- source: CSN-Data-140826-132933.md#page-7 -->

## What must be monitored {#monitoring}

- Secrets Manager high read-rate anomalies on a specific secret (possible credential stuffing)
- Secrets Manager access outside business hours or by unexpected principals — immediate
  security alert
- **Break-glass sessions** — all activity captured; anomalous activity is classified as an
  incident
- Every `POST /admin/config/cache/bust` call, logged with actor identity
- `IsFederal` trigger violations — any violation is an incident
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-19 -->

## Phase 1 scope of the guarantee {#phase-1-scope}

"100% capture" is validated in Phase 1 specifically against the demo's SNP
application-to-approval flow. Broader system-wide completeness is expected to be continuously
verified as functionality is added.
<!-- source: 07_FRD_Audit_Trail.md#section-5 -->

Out of scope for Phase 1: long-term archival/retention tooling beyond the append-only
guarantee, automated compliance reporting or export beyond the on-screen timeline, and
search/analytics across the audit trail at scale.
<!-- source: 07_FRD_Audit_Trail.md#section-6 -->

## A claim in the customer deck not corroborated by engineering docs {#s3-object-lock}

The customer-facing deck states that audit records are protected with **S3 Object Lock (WORM)
for long-term retention** and describes the trail as "tamper-evident by design."
<!-- source: NextGenOverviewEngineering.md#slide-11 -->

No engineering document in this corpus specifies S3 Object Lock, WORM retention, or a
tamper-evidence mechanism (such as hash chaining) for the audit tables. The engineering
position is that immutability is achieved by having no UPDATE or DELETE path, plus database
role separation — which is a weaker property than tamper-evidence. See
`99-contradictions-and-open-questions.md#worm`.

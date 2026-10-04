# The workflow engine

The single largest engineering bet in Phase 1: **the review process is described as data, not
hardwired as program logic.** States differ in how they run application review, and the
platform accommodates that through configuration rather than custom code per state.
<!-- source: 04_FRD_Review_Workflow.md#section-1 -->

## Shape {#shape}

A thin executor that reads a table, evaluates conditions, checks permissions and fires
actions. **The engine code never changes when a state's workflow changes — only the data rows
do.**
<!-- source: CSN-Workflow Engine-140826-132724.md#page-1 -->

Five tables in `cnp_global` hold the definition, one in `cnp_ops` holds per-state variation:

| Table | Location | What it holds |
|---|---|---|
| `WorkflowEntityTypes` | cnp_global | Entity code, plus the `ConditionEvaluator` / `ActionExecutor` class names the engine calls for it |
| `WorkflowStates` | cnp_global | StateCode, display label, `IsFederal`, `IsTerminal`, display colour/order |
| `WorkflowTransitions` | cnp_global | From/To state, TransitionCode, `IsFederal`, `IsAutomatic`, `TriggerEvent`, `RequiresComment`, button label |
| `WorkflowTransitionConditions` | cnp_global | Named hook code, PreCondition/PostCondition, JSONB params, `IsFederal`, user-facing failure message |
| `WorkflowTransitionActions` | cnp_global | Named hook code, `ExecutionOrder`, JSONB params, `IsFederal`, `IsRollbackable` |
| `TenantTransitionOverrides` | cnp_ops | Per-tenant `OverrideType` + JSONB params + who enabled it and when |
<!-- source: CSN-Workflow Engine-140826-132724.md#page-1 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-2 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-3 -->

`WorkflowRolePermissions` joins transitions to role codes with a nullable `TenantCode` (null =
platform-wide). A tenant can add roles to a transition via an `AddRole` override, but cannot
remove a role marked `IsFederal = true`.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-3 -->

## Named hooks, not an expression language {#named-hooks}

Conditions and actions are stored as **named hook identifiers** (`NoNDLMatch`,
`FreezeClaimLaws`, `AllClaimErrorsResolved`) which the engine resolves to a compiled C#
implementation at runtime. An expression language (NCalc, MVEL, a custom DSL) was explicitly
rejected.

The reasoning, in order of weight:

1. **Federal math must never be encoded in configuration strings.** If it is, it can be
   configured differently for a state.
2. **Named hooks are testable.** Each hook is a C# class with unit tests. A runtime-evaluated
   expression is not independently testable.
3. **Named hooks are auditable.** The codebase is the authoritative record of what each hook
   does. An expression language puts business logic in the database, where it can be changed
   without a deployment review.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-4 -->

The consequence, stated as a deliberate asymmetry: *"data drives WHICH hooks run; code
defines WHAT they do. Adding a new state to the claim lifecycle requires a data row. Adding a
new condition requires both a data row AND a code implementation. This is intentional.
Configuration is fast; extending the hook library requires review."*
<!-- source: CSN-Workflow Engine-140826-132724.md#page-14 -->

The configuration team cannot define their own hooks — they select from the registered
catalog via the Workflow Override API (`GET /workflow/hooks`).
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-5 -->
<!-- source: CSN-Code Deployment vs Configuration-140826-133128.md#page-2 -->

Hook names must be stable; renaming requires a migration of the condition and action tables.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-5 -->

### Condition hooks (examples) {#condition-hooks}

| ConditionCode | What it checks | IsFederal |
|---|---|---|
| `AllClaimErrorsResolved` | No `ClaimErrors` rows with `BrokenInd = true` for this claim | Yes |
| `NoOpenSeriousDeficiency` | Sponsor has no active SerDef proceeding | Yes |
| `ISPMeetsThreshold` | CEP group ISP ≥ 40% | Yes |
| `VCAChecklistPassed` | VCA checklist score meets approval threshold | Yes |
| `HasRole` | Requesting user holds the specified role for this tenant | No |
| `NotPastDueDate` | Today is on or before the claim period due date | No |
| `PastLateClaimCutoff` | Today exceeds N days past claim period end | No |
| `AllRequiredDocsAttached` | All required document types attached and Accepted | No (base); federal instances exist |
| `DaysInStatePast` | Entity has been in its current state longer than N days | No |
<!-- source: CSN-Workflow Engine-140826-132724.md#page-12 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-16 -->

### Action hooks (examples) {#action-hooks}

| ActionCode | What it does | IsFederal |
|---|---|---|
| `FreezeClaimLaws` | Locks the sponsor's eligibility tier into a `ClaimLaws` record | Yes |
| `LockRecord` | Sets `IsLocked = true`; blocks all further field edits | Yes |
| `CreateEntitySnapshot` | Writes current field values as JSONB to `EntitySnapshots` | Yes |
| `TriggerValidation` | Runs claim validation, writes `ClaimErrors` rows | Yes |
| `CreateDisbursementRecord` | Creates a pending `Disbursements` row | Yes |
| `SendNotification` | Writes to `NotificationQueue` with a template code | No |
| `AssignReviewer` | Runs reviewer assignment logic | No |
| `AutoDecline` | Fires the Deny transition automatically with a system comment | No |
<!-- source: CSN-Workflow Engine-140826-132724.md#page-12 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-13 -->

## Execution semantics {#execution}

The condition-evaluation steps are the guardrail enforcement points: if a condition fails,
the transition is rejected **before any state change is written**, and the entity remains in
its current state.

**Actions are transactional.** The status change and the actions run inside a single database
transaction. If `FreezeClaimLaws` fails, the status change rolls back and the claim stays in
`UnderReview`. The `IsRollbackable` column flags which actions support compensation logic if
a downstream action fails after they have committed.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-17 -->

This is reinforced at the requirements level: a review step that fails its condition halts the
process at that point, and **no partial change is recorded as if it had succeeded**.
<!-- source: 04_FRD_Review_Workflow.md#section-4 -->

## The eleven entity types {#entity-types}

`Claim`, `SponsorApp`, `SiteApp`, `LateClaimException`, `AdminReview`, `ProcurementReview`,
`CACFPFinancialReview`, `CorrectiveAction`, `Appeal`, `WaiverRequest`, `CapExpRequest`. Each
names its own `ConditionEvaluator` and `ActionExecutor` and the programs it applies to.
`CACFPFinancialReview` is spawned by an action hook on the `AdminReview →
FindingsDocumented` transition when financial findings are present, as a separate workflow
instance linked by `ParentEntityId`.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-4 -->

## Override types and what the guardrail rejects {#override-types}

| OverrideType | What it does | Rejected if |
|---|---|---|
| `Disable` | Stops a transition appearing or firing for this tenant | `WorkflowTransitions.IsFederal = true` |
| `MakeAutomatic` | Manual transition becomes automatic when conditions met | `WorkflowTransitions.IsFederal = true` |
| `AddCondition` | Adds a pre-condition to an existing transition | Target condition `IsFederal = true` |
| `RemoveCondition` | Removes a non-federal pre-condition | Target condition `IsFederal = true` |
| `ReplaceCondition` | Swaps condition params (e.g. a day threshold) | Target condition `IsFederal = true` |
| `AddAction` | Adds an action firing on this transition | Target action `IsFederal = true` |
| `RemoveAction` | Removes a non-federal action | Target action `IsFederal = true` |
| `ChangeRole` | Changes which roles can trigger a transition | `WorkflowRolePermissions.IsFederal = true` |
| `AddRole` | Adds a role that can trigger a transition | `WorkflowTransitions.IsFederal = true` |
<!-- source: CSN-Workflow Engine-140826-132724.md#page-18 -->

Where a state needs a genuinely new intermediate state (Virginia's `DirectorReview` on late
claim exceptions), the pattern is: `Disable` the platform transition, then add tenant-scoped
`WorkflowTransitions` rows with `TenantCode` set.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-16 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-17 -->

## Worked per-state overrides {#state-examples}

| State | Override | Why it is safe |
|---|---|---|
| Maine | Auto-decline claims past a 60-day late cutoff (`AddCondition` on `SubmitClaim`) | `SubmitClaim.IsFederal = false` |
| Hawaii | Escalate stale review after 5 business days instead of 10 calendar (`ReplaceCondition` on `DaysInStatePast`) | Escalation is not federal |
| Alaska | Site affidavit required before approval (`AddCondition` / `AllRequiredDocsAttached`) | State document requirement |
| Wisconsin | Director alert on late-claim-exception approval (`AddAction` / `SendNotification`) | Notifications are not federal |
| Indiana | DirectVer sponsor-facing DC resolution transitions enabled | DirectVer states are not federal |
| Utah | Section 4/11 split enforced on FNS-10 generation (`AddCondition`) | Report generation transitions are not federal |
| Montana | Supervisor review disabled on claims (`Disable`) | Optional transition |
| All states | **Cannot** remove `Approved→Locked`, remove `FreezeClaimLaws`, or bypass `AllClaimErrorsResolved` | All three are `IsFederal = true` |
<!-- source: CSN-Workflow Engine-140826-132724.md#page-10 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-16 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-17 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-21 -->

## Configuration patterns that need no new table {#patterns}

- **Document gates** are `WorkflowTransitionConditions` rows with
  `ConditionCode = 'AllRequiredDocsAttached'`; the JSONB params carry `requiredTypes`,
  `anyOf` and `minCount`. No separate table.
- **Notification rules** are `SendNotification` action rows; multiple notifications on one
  transition use different `ExecutionOrder`. Params carry `templateCode`, `recipientRole`,
  `delayDays` and `suppressIfResolved` (cancel the delayed send if the entity leaves the state
  first). Delayed sends are scheduled via Hangfire.
- **Timeouts and escalation** are self-transitions (`FromState == ToState`) with
  `TriggerEvent = 'OnSchedule'` and a `DaysInStatePast` condition. A nightly Hangfire job
  evaluates all pending automatic transitions.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-14 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-15 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-16 -->

## Professional Services governance {#ps-governance}

PS creates `TenantTransitionOverrides` through an internal admin UI accessible only to LINQ
staff. Every write requires a **justification of at least 20 characters**; the write service
returns 400 if empty and validates the length. A blocked-phrase list ("N/A", "per request",
"test") produces a non-blocking UI warning. The justification is written to `AuditLogs` in an
autonomous transaction so it survives a rollback of the override write itself, and cannot be
edited afterwards — corrections require a new entry.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-19 -->

Three PS roles: `PS_Configurator` (create/edit overrides, view audit log — cannot modify
platform `WorkflowStates`/`WorkflowTransitions` rows or delete audit records), `PS_Lead` (all
of the above plus override approval — cannot modify `IsFederal` flags or bypass guardrails),
`PS_ReadOnly` (view diagrams and override history).
<!-- source: CSN-Workflow Engine-140826-132724.md#page-19 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-20 -->

An optional **two-person rule** can be enabled per tenant: overrides are staged until a
`PS_Lead` approves, and the approving lead cannot be the person who created the override.
Recommended for nTIG-contract tenants. Engineering sets the flag per tenant in a migration —
`PS_Lead` cannot self-enable it.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-20 -->

## The boundary with the Rules Engine {#rules-engine-boundary}

Two systems evaluate conditions and route work. Without a documented boundary a developer
adding a routing requirement has no guidance, and the two risk duplicating or contradicting
each other.

- **Workflow State Machine (named hooks)** answers *"can this transition happen?"* and *"what
  must happen atomically when it does?"* Synchronous, inside the database transaction. A
  condition returning false blocks the transition entirely.
- **Rules Engine (Microsoft Rules Engine, JSONB rule sets)** answers *"given that this
  transition completed, what operational work follows?"* Asynchronous, after the transaction
  commits, via a Hangfire background job. **Cannot block or roll back a transition.** Examples:
  assignment routing, escalation timers, notification triggers.

The decision test, in order: does it need to prevent a transition → condition hook. Does it
need to run in the same transaction → action hook. Does it fire after a transition and cannot
roll it back → Rules Engine. Is it a display/queue-routing concern → Rules Engine or
`ICnpPermissionService`.

*"Synchronous/transactional vs. asynchronous/post-commit is the sharpest line between the two
systems. If a rule needs to be synchronous and transactional, it belongs in a named hook.
There are no exceptions."*
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-13 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-14 -->

Explicitly out of scope for the Rules Engine: federal compliance math (never in JSONB rule
sets — only named hooks with `IsFederal = true`), anything that must run in a transaction, and
anything needing pre-transition state.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-14 -->

This boundary must be enforced in code review: a PR that puts assignment logic in a named
hook, or a blocking condition in the Rules Engine, should be rejected.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-14 -->

The Rules Engine document adds a rule-labelling scheme: `FEDERAL_IMMUTABLE` (in code,
readable but not editable), `FEDERAL_CONFIGURABLE` (federal minimum with admin-configurable
additions), `STATE_CONFIGURABLE`, `TENANT_CONFIGURABLE`. Admin screens surface only the last
two as editable.
<!-- source: CSN-Rules Engine-140826-132727.md#page-3 -->

## `StatusTransitionRules` — the lightweight companion {#status-transition-rules}

Added July 2026 after review of CTS stored procedures. CTS has a `status_get` stored procedure
per form type that hardcodes which statuses are valid next steps; that logic was missing from
the greenfield design as a data table.

`StatusTransitionRules` (cnp_global) carries `FormTypeCode`, `FromStatusCode`, `ToStatusCode`,
`IsManual`, `TenantCode`. It serves two purposes `WorkflowTransitions` is too heavy for: UI
queries for which buttons to show, and API pre-validation of status-change requests before the
full engine runs (including admin bulk operations that do not go through the engine).

Every `StatusTransitionRules` row has a corresponding `WorkflowTransitions` row. **They stay
in sync by convention** — a migration adding a transition adds a row to both.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-23 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-24 -->

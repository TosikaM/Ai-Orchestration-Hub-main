<!-- PROJECT CONTEXT — synthesised, not a source document.

     Every factual claim here needs a provenance comment naming where it came from:
         <!-- from: knowledge/distilled/<topic>.md#<anchor> -->
     `python scripts/project-context.py check` fails on a claim without one.

     If a statement has no source, it is an ASSUMPTION. Move it to 06-open-questions.md
     with the assumption stated, rather than leaving it here where the next reader will
     take it for a requirement. -->

# Domain model

Scoped to what Phase 1 builds. The full platform is ~1,015 operational tables per state; Phase 1
targets **~20–30 `cnp_global` and ~60–80 `cnp_ops` tables, with other domains shipped as empty
migration stubs.**
<!-- from: knowledge/distilled/05-data-architecture.md#collapse -->

## The tenancy model {#tenancy}

Two databases. `cnp_global` holds federal codes, rates, program definitions, the workflow state
machines, the RBAC catalog and the form/review engine catalogs. `cnp_ops` holds all operational
data, **one schema per state**.
<!-- from: knowledge/distilled/05-data-architecture.md#split -->

**There is no `TenantId` column anywhere in Aurora.** The schema name *is* the tenant, so
cross-state access is structurally impossible rather than policy-controlled. The rejected
alternative — a shared schema with a TenantId — fails silently and catastrophically when a
single WHERE clause is missing.
<!-- from: knowledge/distilled/05-data-architecture.md#tenant-boundary -->

`TenantCode` exists in exactly one place: the CDC pipeline adds it during replication to
Snowflake, where all states are aggregated by design.
<!-- from: knowledge/distilled/05-data-architecture.md#tenant-boundary -->

## The data spine {#spine}

`ProgramGroups → ProgramGroupYears → ProgramGroupEnrollments`. **Every Application and every
Claim FK-chains through `ProgramGroupYears`** — it is the universal join key, and it exists so
that every record can answer two questions consistently: which federal program, and which
school year.
<!-- from: knowledge/distilled/05-data-architecture.md#spine -->

## Entities {#entities}

| Entity | Description | Key fields | Where |
|---|---|---|---|
| `ProgramGroups` | Master list of federal programs. Changes only if USDA creates a new program | ProgramCode, name | cnp_global |
| `ProgramGroupYears` | One row per program + year, with boundaries. Carries no operational state | ProgramGroupYearId, ProgramCode, StartDate, EndDate, year label | cnp_global |
| `ProgramGroupEnrollments` | One row per sponsor enrolled in a program year — the record that says a sponsor is a valid participant | SponsorId, ProgramGroupYearId, StatusCode, termination codes | cnp_ops |
| `TenantProgramYearStatus` | Each state's operational status for a program year, tracked independently | ProgramGroupYearId, TenantCode, StatusCode, UpdatedAt, UpdatedBy | cnp_ops |
| `Applications` | The sponsor's annual application | ApplicationId, SponsorId, ProgramGroupYearId, StatusCode | cnp_ops |
| `ClaimLaws` | The immutable snapshot created at approval | ClaimLawId, ApplicationId, eligibility tier, EffectiveDate | cnp_ops |
| `ClaimRateAmounts` | Federal reimbursement rates, effective-dated | ProgramCode, MealType, EligCategory, Rate, EffectiveDate | cnp_global |
| `ProgramRatePeriods` | Per-program rate-period boundaries | ProgramCode, StartDate, EndDate | cnp_global |
| `NdlCheckResults` | Written on every approval attempt, retained permanently | ResultId, ApplicationId, CheckDate, MatchStatus, MatchDetails, CheckedBy | cnp_ops |
| `NdlOverrideRequests` | Human investigation of a PossibleMatch | OverrideId, ResultId, RequestedBy, ReviewedBy, Disposition, Justification | cnp_ops |
| `AuditLogs` | Every user action and system event | AuditId, TenantCode, EntityType, EntityId, ChangeType, ChangedBy, ChangeDate, SessionId | cnp_ops |
| `EntitySnapshots` | Full JSONB snapshot at each status transition | SnapshotId, EntityType, EntityId, StatusCode, SnapshotDate, DataJson, TriggeredBy | cnp_ops |
| `FieldChangeLog` | Every individual field edit, including intra-status | ChangeId, EntityType, EntityId, FieldName, OldValue, NewValue, ChangedBy, ChangedAt, ChangeSource | cnp_ops |
<!-- from: knowledge/distilled/05-data-architecture.md#spine -->
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#claimlaws-contents -->
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#ndl-recording -->
<!-- from: knowledge/distilled/07-audit-and-immutability.md#tables -->

### Workflow engine entities {#workflow-entities}

| Entity | Key fields | Where |
|---|---|---|
| `WorkflowEntityTypes` | EntityTypeCode, ConditionEvaluator, ActionExecutor | cnp_global |
| `WorkflowStates` | StateCode, StateName, **IsFederal**, IsTerminal, DisplayColor, DisplayOrder | cnp_global |
| `WorkflowTransitions` | FromStateId, ToStateId, TransitionCode, **IsFederal**, IsAutomatic, TriggerEvent, RequiresComment, TransitionName | cnp_global |
| `WorkflowTransitionConditions` | ConditionCode, ConditionType, ConditionParams (JSONB), **IsFederal**, FailureMessage | cnp_global |
| `WorkflowTransitionActions` | ActionCode, ExecutionOrder, ActionParams (JSONB), **IsFederal**, IsRollbackable | cnp_global |
| `WorkflowRolePermissions` | TransitionId, RoleCode, TenantCode (null = all tenants) | cnp_global |
| `TenantTransitionOverrides` | TransitionId, TenantCode, OverrideType, OverrideParams (JSONB), EnabledAt, EnabledBy | cnp_ops |
| `StatusTransitionRules` | FormTypeCode, FromStatusCode, ToStatusCode, IsManual, TenantCode | cnp_global |
<!-- from: knowledge/distilled/02-workflow-engine.md#shape -->
<!-- from: knowledge/distilled/02-workflow-engine.md#status-transition-rules -->

### Configuration entities {#config-entities}

| Entity | Key fields | Where |
|---|---|---|
| `ConfigDefinitions` | ConfigKey, ProgramCode, ValueType, DefaultValue, MinValue, MaxValue, AllowedValues, **IsFederal**, Category, Description, FederalCitation, CacheTier | cnp_global |
| `TenantConfigOverrides` | ConfigDefId, TenantCode, ProgramCode, OverrideValue, EffectiveDate, ExpiresDate, SetBy, SetAt, **Justification (required)** | cnp_ops |
| `Errors` | ErrorCode, DefaultDescription, DefaultSeverity, ProgramCode, IsActive, **IsFederal** | cnp_global |
| `TenantErrorConfig` | TenantCode, ErrorId, OverrideDescription, OverrideType, StartDate, EndDate, ModifiedBy | cnp_ops |
<!-- from: knowledge/distilled/03-configuration-model.md#configdefinitions -->
<!-- from: knowledge/distilled/03-configuration-model.md#tenant-overrides -->
<!-- from: knowledge/distilled/03-configuration-model.md#tenant-error-config -->

### Rights entities {#rights-entities}

| Entity | Key fields | Where |
|---|---|---|
| `PermissionCatalog` | PermissionCode (dotted), Domain, SubArea, Action, Description, IsActive | cnp_global |
| `RoleDefinitions` | RoleCode, RoleName, ScopeConstraint (CrossTenant / SingleTenant / SponsorOnly) | cnp_global |
| `RolePermissions` | RoleId, PermissionId, **IsFederal**, IsDefault | cnp_global |
| `TenantRoleDefinitions` | TenantCode, RoleCode, ScopeConstraint, CreatedBy, IsActive | cnp_ops |
| `TenantRolePermissions` | TenantRoleId, PermissionId, GrantedBy, GrantedAt | cnp_ops |
| `TenantRoleOverrides` | RoleId, PermissionId, TenantCode, OverrideType (Grant/Revoke), EnabledBy, **Justification** | cnp_ops |
| `UserRoleAssignments` | UserId, RoleId **or** TenantRoleId (exactly one), TenantCode, ScopeType, SponsorId, DomainScope, ExpiresAt | cnp_ops |
| `UserPermissionOverrides` | UserId, PermissionId, TenantCode, OverrideType, Reason, GrantedBy, ExpiresAt | cnp_ops |
<!-- from: knowledge/distilled/04-identity-and-rights.md#permission-structure -->
<!-- from: knowledge/distilled/04-identity-and-rights.md#override-layers -->
<!-- from: knowledge/distilled/04-identity-and-rights.md#tenant-roles -->

## Relationships {#relationships}

| From | Cardinality | To | Notes |
|---|---|---|---|
| ProgramGroups | 1 → many | ProgramGroupYears | One row per program per year |
| ProgramGroupYears | 1 → many | ProgramGroupEnrollments | The enrollment record lives per state |
| ProgramGroupYears | 1 → many | Applications | The spine FK every entity chains through |
| Sponsor | 1 → many | ProgramGroupEnrollments | One sponsor, one row per program — not a comma-separated list |
| Application | 1 → **exactly 1** | ClaimLaws | Created automatically on approval; never more, never fewer |
| Application | 1 → many | NdlCheckResults | One per approval *attempt*, not per application |
| NdlCheckResults | 1 → 0..1 | NdlOverrideRequests | Only a PossibleMatch produces one |
| WorkflowTransitions | 1 → many | WorkflowTransitionConditions | Evaluated before the transition; any failure blocks it |
| WorkflowTransitions | 1 → many | WorkflowTransitionActions | Fired in `ExecutionOrder` inside the transaction |
| WorkflowTransitions | 1 → many | TenantTransitionOverrides | Per-state variation, guardrail-checked at write |
| StatusTransitionRules | 1 → 1 | WorkflowTransitions | Kept in sync **by convention**, not by constraint |
| Application | 1 → many | AuditLogs / EntitySnapshots / FieldChangeLog | Every consequential action, successful or blocked |
<!-- from: knowledge/distilled/05-data-architecture.md#spine-rationale -->
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#immutability -->
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#ndl-mechanism -->
<!-- from: knowledge/distilled/02-workflow-engine.md#execution -->
<!-- from: knowledge/distilled/02-workflow-engine.md#status-transition-rules -->
<!-- from: knowledge/distilled/07-audit-and-immutability.md#completeness -->

## Program year boundaries {#program-years}

Not one calendar. Getting this wrong produces claims that resolve to the wrong rate.

| Program | Program year |
|---|---|
| NSLP, SBP | 1 July – 30 June |
| CACFP | 1 October – 30 September |
| SFSP | Seasonal (May–Sept operating); **rate** cycle 1 Jan – 31 Dec |

This is **not** the Federal Fiscal Year (1 Oct – 30 Sep), which governs funding allocations and
FNS reporting and must not appear in `StartDate`/`EndDate` for school nutrition programs.
<!-- from: knowledge/distilled/05-data-architecture.md#program-years -->

`ProgramRatePeriods` exists because one effective date on `ClaimRateAmounts` cannot express
both cycles. It is intentionally decoupled from `ProgramGroupYears` — a CACFP program year
running October–September will have rate-period rows starting 1 July, and **that is correct by
design.**
<!-- from: knowledge/distilled/05-data-architecture.md#program-years -->

## Naming decisions {#naming}

The client's vocabulary wins. Where a technical instinct would rename something, it does not.

| Client's term | Means | Do not call it |
|---|---|---|
| **Sponsor** | The participating organization — a school district, daycare centre, camp operator | Customer, organization, applicant |
| **Site** | A location where meals are served | Location, facility, branch |
| **ClaimLaws** | The immutable eligibility snapshot frozen at approval | Snapshot, rate lock, frozen rates |
| **IsFederal** | The structural lock on anything federally mandated | Locked, readonly, system |
| **CnpDefaults** | The ~3,000 typed operational config values | Settings, feature flags, parameters |
| **Named hook** | A compiled C# condition or action referenced by name from a data row | Rule, handler, callback |
| **Program Year** | The program's own year boundary, which is not the fiscal year | Fiscal year, school year, FY |
| **Tenant** | One state agency, one `cnp_ops` schema | Customer, org, account |
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#product -->
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#claimlaws-problem -->
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#decision -->
<!-- from: knowledge/distilled/03-configuration-model.md#three-systems -->
<!-- from: knowledge/distilled/02-workflow-engine.md#named-hooks -->
<!-- from: knowledge/distilled/05-data-architecture.md#program-years -->

Two naming conflicts are **unresolved** and must not be settled by whoever types first:
`Declined` vs `Denied` as the terminal state code, and `ProgramMealRates` vs `ClaimRateAmounts`
as the rate table. Both are in [06-open-questions.md](06-open-questions.md).

## Structural constraints on the schema {#constraints}

- **Every financial column is `DECIMAL(18,2)`.** No FLOAT, no REAL, no NUMERIC without explicit
  precision. A script casting a financial value to float is a bug to reject.
- **Audit tables are partitioned from day one** and are append-only; schema changes add columns
  only — no renames, no type changes, no drops.
- **`SeriousDeficiency` lives in its own `[serdef]` schema** so no other domain's queries can
  modify it — a regulatory audit boundary, not a tidiness preference.
- **DC feed staging tables need a unique index on `SourceRowHash CHAR(64)`** per state schema,
  for idempotency on retries.
- **Referential integrity moves to the API layer** for anything collapsed into `LookupCodes` or
  stored in `FormFieldValues`. There is no database-level backstop, and this is an accepted
  cost, not an oversight.
<!-- from: knowledge/distilled/05-data-architecture.md#hard-requirements -->
<!-- from: knowledge/distilled/05-data-architecture.md#serdef -->
<!-- from: knowledge/distilled/05-data-architecture.md#collapse -->
<!-- from: knowledge/distilled/07-audit-and-immutability.md#iauditservice -->

## What ClaimLaws contains — unresolved {#claimlaws-open}

The single most consequential open question in the domain model. Three documents say
`ClaimLaws` stores the eligibility tier and **not** dollar rates; the reference C#
implementation reads dollar rates directly off the ClaimLaws object. **Do not design this table
until it is answered** — see [06-open-questions.md](06-open-questions.md).
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#claimlaws-contents -->

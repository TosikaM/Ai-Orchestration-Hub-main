# The federal guardrail: `IsFederal`

This is the single most load-bearing concept in the platform. Everything else — the workflow
engine, the config hierarchy, the rights model — is designed to be flexible, and `IsFederal`
is the mechanism that stops that flexibility from reaching federal law.

## The decision {#decision}

`IsFederal = true` is a **structural lock** applied at four levels:

| Level | Table |
|---|---|
| Config values | `ConfigDefinitions` |
| Workflow states | `WorkflowStates` |
| Workflow transition conditions and actions | `WorkflowTransitionConditions`, `WorkflowTransitionActions` |
| Permission catalog entries | `PermissionCatalog` |

When `IsFederal = true`, no tenant override is accepted — the API returns HTTP 403 with a
federal citation. **No override mechanism exists.** This is enforced in code, not policy.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-9 -->

A fifth surface is documented separately: `RolePermissions.IsFederal` protects specific
role-permission pairs from tenant or user override.
<!-- source: CSN-CNP Rights-140826-132801.md#page-11 -->

And a sixth: `Errors.IsFederal` blocks a state from downgrading a federally required
validation error to a warning. Description overrides remain allowed.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-10 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-11 -->

## Why a hard block and not a warning {#rationale}

The CEP ISP multiplier (1.6×) is mandated by 42 USC 1759a. It is not a reasonable default, it
is a legal requirement — allowing a state to configure it to 1.5× would silently produce
incorrect reimbursements for every CEP school in that state.

Three alternatives were considered and rejected:

- **Warning UI with acknowledgment** — the user dismisses the warning; the misconfiguration
  still occurs.
- **Approval workflow for federal overrides** — adds a human gate, which introduces the risk
  that a reviewer approves an incorrect override in good faith.
- **Audit-only, no block** — detects the problem after incorrect reimbursements have already
  been submitted to FNS.

The stated reasoning for the hard block is that it is *"the only control that survives staff
turnover, onboarding errors, and edge cases where an administrator believes they are making a
legitimate change."*
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-9 -->

`FederalCitation` is stored alongside the lock, so the block is auditable and defensible to
FNS rather than just being an opaque refusal.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-9 -->

## Enforcement is layered, and the layers are not equivalent {#layers}

The customer-facing deck states enforcement at three independent layers — UI, API, and
database trigger.
<!-- source: NextGenOverviewEngineering.md#slide-3 -->

The engineering documents are more precise about what each layer is *for*:

**UI suppression is a usability feature, not security.** Federal controls are hidden or
disabled before any API call is made, but the actual enforcement is the API write-service
guardrail check and the PostgreSQL trigger. Both fire regardless of how the write arrives.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-22 -->

**The API guardrail only fires when the write passes through the API.** A direct `INSERT INTO
TenantTransitionOverrides` from a SQL client, a data-fix migration, or a CI/CD deployment
script bypasses it entirely. This is precisely why the database layer exists.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-6 -->

**The database triggers are the last line of defence.** Two `BEFORE INSERT OR UPDATE`
triggers:

- `trg_block_federal_transition_override` on `TenantTransitionOverrides`
- `trg_block_federal_config_override` on `TenantConfigOverrides`

Both call `log_federal_guardrail_violation()` and raise a PostgreSQL exception. The audit
insert runs in an **autonomous transaction**, so the rollback of the rejected write does not
erase the audit record — every blocked attempt produces an `AuditLogs` row with
`EntityType = 'FederalGuardrailViolation'`, the source role, the targeted table, the rejected
values and a timestamp.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-6 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-8 -->

Coverage by write source:

| Write source | Application guardrail | Database trigger |
|---|---|---|
| API call through write service | Yes | Yes |
| Direct SQL via SQL client (DBA, engineer) | No | Yes |
| Migration script run during deployment | No | Yes |
| Runbook or data-fix script | No | Yes |
| ORM or query builder bypassing the service layer | No | Yes |
<!-- source: CSN-Workflow Engine-140826-132724.md#page-8 -->

**Never disable these triggers.** Any migration that DROPs, DISABLEs or modifies either
trigger must be blocked at review, and DBAs must verify trigger integrity after every
migration that touches the override tables.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-3 -->

## The flag itself is not configurable {#flag-is-not-configurable}

`IsFederal` is set at system deployment and can only be changed via a versioned database
migration reviewed by a senior engineer. It is never exposed in the admin UI. A state agency
administrator cannot see or change it. LINQ engineering owns the list of federal locks.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-6 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-10 -->

## Belt and suspenders on config bounds {#bounds}

For federally locked numeric values, `MinValue` and `MaxValue` are both set equal to
`DefaultValue` — `CEP.ISPMultiplier` has `Min = Max = Default = 1.6`,
`FederalCitation = '42 USC 1759a'`. This makes it arithmetically impossible to write a
different value even for a user who somehow has override permission: the bounds validation
rejects anything outside `[1.6, 1.6]`. *"The IsFederal flag is the belt; the bounds are the
suspenders."*
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-4 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-7 -->

## What is federally locked {#the-locked-set}

Named explicitly across the corpus:

| Item | Nature of the lock |
|---|---|
| CEP claiming formula, ISP × 1.6 capped at 100% | 42 USC 1759a §(a)(1)(F)(viii) |
| Free/reduced income thresholds (130% / 185% of poverty) | Federal percentage |
| The NDL check on application approval (`NoNDLMatch`) | Non-negotiable regardless of state config |
| 60-day claim submission deadline | States cannot extend it via configuration |
| SFSP 2% second-meal cap | Federal rule |
| `Approved → Locked` transition on claims | Cannot be disabled |
| `FreezeClaimLaws` action | Cannot be removed |
| `AllClaimErrorsResolved` condition | A state cannot approve a claim with unresolved errors |
| Section 4/11 split formula | FNS-10 reporting requirement |
| DCH Tier I/II determination | Census-based federal methodology |
| Non-congregate PY2024 gate | Federal regulation |
| `Compliance.ReviewCycleYears` = 3 | 7 CFR 210.18(b) |
| `CACFP.MealLimitPerChildPerDay` = 3 | 7 CFR 226.20 |
| FDCH Tier I certification windows (60 months evidence-based / 12 months income-based) | Cannot be shortened by state config |
| FNSAuditor read access to any record being audited | A state cannot restrict this |
| `StateAgencyAdmin` → `SNP.Applications.Approve` | A state cannot remove approval capability from the Admin role |
| `Reviewer` → `Compliance.Reviews.Create` | A state cannot prevent reviewers initiating reviews |
<!-- source: CSN-Rules Engine-140826-132727.md#page-2 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-5 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-17 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-6 -->
<!-- source: CSN-Data-140826-132933.md#page-7 -->
<!-- source: CSN-CNP Rights-140826-132801.md#page-11 -->

## A distinction that is easy to get wrong {#isfederal-is-not-permanence}

`IsFederal` on a `RolePermission` means the permission cannot be removed **from the role**. A
user can still lose the permission by having their role assignment revoked. It protects the
role definition, not the user assignment: a state agency can remove someone from the Reviewer
role; it cannot make the Reviewer role unable to create compliance reviews.
<!-- source: CSN-CNP Rights-140826-132801.md#page-11 -->

## What this costs {#consequences}

The list of `IsFederal = true` values must be maintained as federal regulations change. In
particular, **an annual FNS rate update that changes a locked value requires a platform
deployment — it cannot be config-updated.**
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-10 -->

## The CI gate that keeps it honest {#ci-gate}

A GitHub Actions status check scans every PR diff for an added line containing
`IsFederal=true` (catching C#, SQL and JSON seed formats). If found with no test file in the
PR, the merge is blocked. An onshore tech lead may apply a `guardrail-test-exempt` label to
bypass it; the bypass is written to a timestamped audit entry in the Actions run summary, and
offshore engineers cannot apply the label (it requires the Triage+ repo role).
<!-- source: CSN-Prototype-140826-133159.md#page-9 -->

Phase 1 must ship **seven required guardrail assertions**, passing in CI.
<!-- source: CSN-Prototype-140826-133159.md#page-18 -->

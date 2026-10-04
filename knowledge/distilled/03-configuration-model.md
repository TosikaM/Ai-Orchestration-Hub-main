# The configuration model

## The problem being solved {#problem}

CTS has approximately **3,000 hardcoded values** spread across stored procedures, application
config files, and database rows in a loosely structured defaults table — no consistent
resolution order, no validation bounds, no effective dating. Adding a new state requires
locating and replicating all relevant values with no documented process.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-5 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-1 -->

The business goal: a state's authorized staff changes a setting themselves and sees it take
effect across the live system within minutes, with zero developer involvement, while anything
federally mandated stays untouchable.
<!-- source: 02_FRD_Configuration_Management.md#section-1 -->

## Three systems that must not be conflated {#three-systems}

This distinction is stated emphatically in three separate documents, which is a signal that
conflating them is the expected failure.

| System | Question it answers | Scale | Where |
|---|---|---|---|
| **Feature flags (LaunchDarkly)** | *Does this module exist for this tenant?* | ~47 flags, on/off | External service + local cache |
| **CnpDefaults** | *What value does this feature use?* | ~3,000 typed scalars | `ConfigDefinitions` / `TenantConfigOverrides` |
| **Workflow overrides** | *How does this state's process differ?* | State-machine rules as data | `TenantTransitionOverrides` |
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-1 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-6 -->

*"Whether the late claim cutoff is 60 days or 90 days is not a feature flag question. Both
states have late claim logic, they just use different thresholds. Putting thresholds in
LaunchDarkly would bloat flag management and mix two distinct concerns in one tool."*
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-1 -->

The frontend document adds a third axis with the same warning — feature flags (module level),
form metadata (which sections and fields exist), and Formly field config (required / optional
/ hidden / conditional) are three separate layers. *"Confusing them creates an unmaintainable
system where every field change requires a deployment."*
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-1 -->

## The three-layer hierarchy {#hierarchy}

`ICnpConfigService.GetValue<T>(configKey, tenantCode, programCode?)` resolves in order:

1. **Tenant override** — `TenantConfigOverrides` in `cnp_ops`, effective-dated, most specific
2. **Program default** — `ConfigDefinitions` row with a `ProgramCode`
3. **Platform default** — `ConfigDefinitions` row with `ProgramCode IS NULL`

Layers do not blend or average; the most specific layer that has a value always wins.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-5 -->
<!-- source: 02_FRD_Configuration_Management.md#section-4 -->

The resolution is a `COALESCE` chain with four arms, because the tenant layer itself splits
into tenant+program and tenant-wide:

```
COALESCE(
  tenant + program override (EffectiveDate <= TODAY, most recent),
  tenant-wide override      (EffectiveDate <= TODAY, most recent),
  ConfigDefinitions where ProgramCode = <program>,
  ConfigDefinitions where ProgramCode IS NULL
)
```
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-2 -->

Rationale for each layer: the platform default guarantees every key has a value so no null
reference is possible; the program layer lets CACFP differ from NSLP without per-state
configuration for the difference; the tenant layer allows per-state variation *within the
bounds set at the platform level*.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-5 -->

Rejected alternatives: `appsettings.json` / environment variables (requires a deployment for
every change and cannot be state-specific without per-state deployments), and a single flat
config table with a TenantId (no resolution hierarchy, no program grouping, no bounds).
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-6 -->

## `ConfigDefinitions` — the master catalog {#configdefinitions}

One row per key per program. This table is what turns "3,000 hardcoded values in stored
procedures" into "3,000 documented, typed, bounded configuration keys."

| Column | Purpose |
|---|---|
| `ConfigKey` | Dotted human-readable key: `Claims.LateClaimCutoffDays`, `DC.MatchConfidenceMin` |
| `ProgramCode` | Null = platform-wide; `NSLP` / `SFSP` / `CACFP` = program-specific |
| `ValueType` | `int`, `decimal`, `bool`, `string`, `date` |
| `DefaultValue` | Stored as string, cast at read time |
| `MinValue` / `MaxValue` | Validation bounds; the engine rejects overrides outside them |
| `AllowedValues` | JSONB, for enum-typed keys |
| `IsFederal` | True = tenant cannot override, platform value only |
| `Category` | One of eight, drives admin UI grouping and access control |
| `Description` | Plain-English explanation |
| `FederalCitation` | CFR section if federally prescribed |
| `CacheTier` | `Immediate` / `Session` / `Nightly`; default `Session` |
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-2 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-3 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-8 -->

## `TenantConfigOverrides` — per-state values {#tenant-overrides}

Carries `TenantCode`, nullable `ProgramCode`, `OverrideValue`, `EffectiveDate` (future-datable),
optional `ExpiresDate`, `SetBy`, `SetAt`, and a **required `Justification`**.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-3 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-4 -->

At the requirements level: no setting can be changed anonymously or without explanation, and
every override records who changed it, when it takes effect, and why.
<!-- source: 02_FRD_Configuration_Management.md#section-3 -->

## The eight categories {#categories}

Claims · Direct Certification · Compliance · Applications · Notifications · Reporting ·
Program-Specific · Infrastructure. The category drives admin UI organisation *and* access
control — a state nutrition director should see Claims and Compliance config and should not
see infrastructure config.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-4 -->

Representative keys: `Claims.LateClaimCutoffDays`, `Claims.MaxMealsPerStudentPerDay`,
`DC.MatchConfidenceMin` (85), `DC.PossibleMatchMin` (50), `Compliance.ReviewCycleYears` (3),
`Compliance.FiveDaySampleDaysRequired` (5), `Apps.CapitalExpenditureMin` ($5,000),
`CEP.ISPMultiplier` (1.6, federal, locked), `CACFP.MealLimitPerChildPerDay`,
`DCH.TierINeighborhoodPovPct` (50%), `Notifications.ClaimReminderDays` (7, 3, 1),
`AnnualRateAnomalyMaxPct` (10%).
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-4 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-5 -->

## Effective dating {#effective-dating}

Overrides carry an effective date so a change can be staged in advance without a deployment
window. A Minnesota contract renegotiation changing the late claim cutoff from 60 to 45 days
on 1 July is written in April with `EffectiveDate = 2026-07-01`; between then and 30 June the
engine resolves 60, and from 1 July it resolves 45.

The mechanism needs no scheduled job: the resolution query filters `EffectiveDate <= TODAY()`
and takes the most recent matching row, so future-dated overrides sit in the table harmlessly
until their date arrives and they simply become the winning row in the COALESCE chain. The
old value remains as history.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-5 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-6 -->

The architectural payoff is stated as: *"rate changes are pre-staged and activate
automatically — no emergency deployments on October 1."*
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-5 -->

## Validation bounds {#bounds}

The engine validates any override against `MinValue` / `MaxValue` / `AllowedValues` before
writing the row. This prevents a typo setting the DC confidence threshold to 8 instead of 80,
or the late claim cutoff to 600 days instead of 60.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-6 -->

## Caching — three tiers {#cache}

| Tier | TTL | For | Example |
|---|---|---|---|
| **1 — Immediate** | Redis, 5 min; invalidated on write | Keys where a stale value causes a real-time compliance or eligibility error | `DCMatch.ConfidenceMinimum`, `Claims.FnsSubmissionDeadlineDays`, `NDL.OverrideRequiresApproval` |
| **2 — Session** | Per-request (`IMemoryCache`, request scope), no shared cache | Display, form rendering, UI defaults — must be consistent within one rendered page, cross-request staleness harmless | UI labels, notification content templates |
| **3 — Nightly** | Loaded at startup, refreshed by a Hangfire job at midnight UTC | Values changing annually or semi-annually where a same-day change is operationally impossible | Reimbursement rates, program year start/end, poverty guideline thresholds |
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-7 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-8 -->

Tier assignment is set at key-definition time by LINQ engineering; it is not configurable by
state administrators.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-8 -->

**A Tier 3 emergency override set at 2pm will not take effect until midnight** unless a manual
cache bust is issued — an operational trap worth knowing before a demo.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-8 -->

### Cache bust {#cache-bust}

`POST /admin/config/cache/bust?tenantCode={code}&configKey={key}`. Requires the
`LINQConfigAdmin` role. Logged to `AuditLogs` with `EntityType = 'ConfigCacheBust'`, actor,
tenant, key and timestamp. **Rate-limited to 10 operations per admin per hour** to prevent a
cache stampede. The config write service calls it automatically when an override is saved.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-8 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-9 -->
<!-- source: CSN-Prototype-140826-133159.md#page-15 -->

The requirements layer adds a rate limit on repeated rapid changes to the same setting by the
same admin, for the same reason.
<!-- source: 02_FRD_Configuration_Management.md#section-4 -->

## The single accessor rule {#single-accessor}

`ICnpConfigService.GetValue<T>()` is the **only** sanctioned path. Reading `ConfigDefinitions`
or `TenantConfigOverrides` directly in application code is prohibited, so that three-layer
resolution, bounds validation and caching are always applied — and so that no service
accidentally hardcodes the default value because it forgot to call the config layer.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-7 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-6 -->

## Per-state error configuration {#tenant-error-config}

Added July 2026 after review of CTS stored procedures — there was no per-state configuration
layer for error descriptions, severity overrides or effective dates.

- `Errors` (cnp_global) is the global validation error catalog: `ErrorCode`,
  `DefaultDescription`, `DefaultSeverity` (Error | Warning), `ProgramCode`, `IsActive`,
  `IsFederal`. States read from it and cannot modify it.
- `TenantErrorConfig` (cnp_ops) holds per-state overrides: `OverrideDescription`,
  `OverrideType` (Error | Warning | null), `StartDate`, `EndDate`, `ModifiedBy`.

**A federal error cannot be downgraded to a warning.** The write service checks
`Errors.IsFederal` before accepting an `OverrideType = Warning` write; any attempt is rejected
and logged as a `FederalGuardrailViolation`.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-10 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-11 -->

`TenantErrorConfig` must be verified present in **all existing state schemas** before any
state goes live.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-12 -->

## What needs a deployment and what does not {#deploy-vs-config}

**Configuration — no deployment:** onboard a new state; update annual reimbursement rates
(INSERT into `ClaimRateAmounts`); future-date a config change; register a DC feed credential
update; register an accounting adapter (after the adapter code is deployed); change a state's
late claim cutoff; add a state's auto-decline behaviour; change a notification schedule; grant
a role permission to trigger a transition; enable Session Replay for a state.
<!-- source: CSN-Code Deployment vs Configuration-140826-133128.md#page-5 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-11 -->

**Deployment required:** a new named condition or action hook; a new `WorkflowState`; a new
`IsFederal` row (migration review by a senior onshore engineer); a new external system
integration; **a new config key** (seeded via database migration before operators can set
overrides); changing `IsFederal` on any row; changing any federal math formula; a new module
or program type.
<!-- source: CSN-Code Deployment vs Configuration-140826-133128.md#page-6 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-11 -->

### The named anti-pattern {#anti-pattern}

*"Hardcoding items for states because the Configuration API doesn't support it yet."* The
prescribed response is to add the missing API surface and configure through it. Hardcoding
state-specific logic in application code is exactly what the design exists to eliminate.
<!-- source: CSN-Code Deployment vs Configuration-140826-133128.md#page-6 -->

The Definition of Done for each phase is stated in the same terms: a phase is not complete
until the configuration team can accomplish everything in that phase's scope through the
Configuration API without a code change.
<!-- source: CSN-Code Deployment vs Configuration-140826-133128.md#page-8 -->

## Zero-deployment state onboarding {#onboarding}

`POST /tenants` creates the `cnp_ops` schema and seeds platform defaults.
`POST /tenants/{tenant}/scaffold?similarTo=UT` produces an AI-generated starter config by
similarity to an existing state, which the onshore team reviews and approves.
`GET /tenants/{tenant}/readiness` returns a checklist of unresolved required config and blocks
go-live until it clears.
<!-- source: CSN-Code Deployment vs Configuration-140826-133128.md#page-4 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-6 -->

# The foundational architecture — four layers

Source: `CNP_Foundational_Architecture_v0.1`, dated **30 June 2026** — the most recent document
in the corpus, and the only one that states an explicit layering model. It is version **0.1**,
so it is a draft, but it is a *later* draft than most of what it summarises.
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-1 -->

Its own claim about its status is worth keeping: *"The foundation described above is not
invented; it is what the customer's own documents converge on."* What it adds is the explicit
four-layer model and the mapping between the 17 foundation components and the Phase 1 vertical.
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-12 -->

## The four layers {#layers}

| Layer | What it is | Rule |
|---|---|---|
| **4 — Verticals** | Phase-specific feature slices. Phase 1: SNP application-to-approval, one state. Phase 2: Claims, Federal Reports, all programs and states, the AI layer. Phase 3: Food Distribution, CACFP IMP activation, offline review | Optimised for the phase |
| **3 — Domains** | Program-specific business logic (SNP, CACFP, DCH, SFSP, FFVP, SSFO, CEP) and cross-program domains (Claims, Eligibility, Compliance, Accounting) | Plug into the engines via **named hooks and configuration rows** — never by extending an engine |
| **2 — Engines** | Workflow · Rules · Form · Review Instrument · Federal Report · VCA Instrument | Configurable, data-driven, **zero knowledge of any specific program or state.** All share the IsFederal enforcement contract and read from `cnp_global` |
| **1 — Foundation** | The multi-tenant data plane, identity, authorisation, configuration, secrets, audit, notifications, background jobs, the frontend shell, the adapter contracts, the federal-guardrail pattern, DevOps | Built once. **Nothing in the foundation knows about a specific program, state, or feature** |
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-2 -->

The reason the boundary matters, stated plainly: *"the team building Phase 1 always knows
whether the line of code they are about to write belongs in the foundation (and therefore must
be designed for Phase 2 and beyond) or in the vertical (and therefore can be optimised for the
prototype demo). That single distinction is the difference between a foundation that survives
Phase 2 and a foundation that has to be rebuilt."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-12 -->

**Phase 1 builds Layer 1 in full**, a subset of Layer 2 sufficient to run an application
workflow (Workflow Engine + Form Engine), one Layer 3 domain (SNP, minimum viable), and one
Layer 4 vertical.
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-2 -->

## Why this shape — four forcing principles {#principles}

1. **One codebase, many state footprints.** State variation cannot live in code branches, so it
   lives in configuration rows, feature flags or pluggable adapters — *all three are foundation
   concerns.* The foundation provides the homes; domains and verticals fill them.
2. **Federal guardrails are structural.** Because `IsFederal` is cross-cutting, enforcement
   lives in Layer 1 — the configuration service, the permission service, the workflow service
   — **never in a domain.**
3. **Frozen-at-approval semantics.** Because every program needs the freeze pattern, the
   snapshot mechanism is Layer 1/2 — **never per-program code.**
4. **Database is the tenant boundary.** Tenant scoping is solved once in Layer 1 (`ICnpContext`
   + connection resolution) and used unmodified above.
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-3 -->

## The seventeen foundation components {#components}

### Data plane {#f-data}

| | Component | Phase 1 scope |
|---|---|---|
| F1 | `cnp_global` — all federal-truth data: rates, programs, lookup codes, workflow definitions, rule definitions, form definitions, RBAC catalogue, config keys, query templates. Read by every state | Subset of the ~387 tables seeded: programs, workflow defs, form defs, RBAC catalogue, config keys for the SNP application |
| F2 | `cnp_ops` — per-state operational data. Contract: `ICnpContext.StateDb` | Built for the demo state; **per-state migration runner in place for Phase-2 multi-state** |
| F3 | `cnp_ext` — per-state extension schema for genuinely state-specific tables (Ohio Budget+42, Wyoming gratefdp). **Never referenced from shared platform code** | Scaffolded but unused |
| F4 | Snowflake — read-only mirror via CDC. **All reports, analytics and AI read from Snowflake; operational Aurora is never queried for analytics.** Tenant isolation by row-access policy | Account provisioned, CDC scaffolded, **no Phase-1 read traffic** |
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-3 -->

### Tenant resolution {#f-tenant}

| | Component | Phase 1 scope |
|---|---|---|
| F5 | Tenant resolution chain: subdomain → YARP classifies tenant → `ICnpContext { GlobalDb, StateDb, TenantCode }` injected per request | Built and exercised by the demo state's subdomain |
| F6 | **Tenant Registry** — a provisioning record in `cnp_global` tracking when each state was onboarded, what platform version they run, and which features are active | Single row seeded for the demo state |
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-3 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-4 -->

`TenantRegistry` appears **only in this document.** It is a real addition to the data model.

### Identity, authorisation, secrets {#f-identity}

| | Component | Phase 1 scope |
|---|---|---|
| F7 | **Keycloak** as OIDC broker — one deployment on ECS Fargate brokering all state IdPs. Per-tenant realms federate **ClassLink / Okta / Azure AD** (Phase 1 OIDC-native states) and **SAML/ADFS** (Phase 2 SAML states) | Deployed; one demo-state realm configured |
| F8 | `ICnpPermissionService` — authorisation owned exclusively here. Three-layer override; explicit Revoke beats Grant below; `IsFederal` permissions cannot be revoked | **Phase-1 SECURITY domain seeded with ~25 permissions** |
| F9 | `ISecretProvider` — app code only sees reference paths, never values. Offshore principals structurally denied production paths | Built; **the production interface contract is enforced even though Phase 1 has no production** |
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-4 -->

F7 is the most architecturally detailed statement of the identity decision anywhere in the
corpus — and it names **Keycloak** unambiguously, with the federation model spelled out.

### Configuration and the guardrail {#f-config}

| | Component | Phase 1 scope |
|---|---|---|
| F10 | `ICnpConfigService` — ~3,000 typed, bounded, effective-dated keys; three-layer resolution via COALESCE; three-tier cache | Subset seeded (SNP application keys); 3-tier Redis cache wired |
| F11 | The `IsFederal` pattern — *"every CnpDefault, RolePermission, WorkflowTransition, FormField, and ComplianceRuleDef carries an IsFederal column."* Write-time check in every Layer-1 service; **PR-blocking assertion in tests** | Built and enforced across Config, RBAC and Workflow services |
| F12 | LaunchDarkly — ~47 module-level flags at full scale, evaluated by Angular route guards and backend attributes | ~5 flags wired |
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-4 -->

F11 extends the `IsFederal` surface to **`FormField` and `ComplianceRuleDef`** — two carriers
not named in the earlier architecture documents.

### Audit, notifications, jobs {#f-audit}

| | Component | Phase 1 scope |
|---|---|---|
| F13 | Audit Service — `AuditLogs` (event header), `EntitySnapshots` (full prior-state JSONB), `FieldChangeLog` (field diffs). `IAuditService.Emit(event)` **auto-wired into all Layer-2 engines** | 100% capture for the Phase-1 surface; **Audit Timeline query API live** |
| F14 | Notification Service — outbound only, no business rules. Templates in `cnp_global`. **Triggered by workflow actions, not by domain code** | Minimal templates wired for application-state-change emails |
| F15 | Hangfire — per-tenant scheduled work | **Two Phase-1 jobs registered: nightly synthetic-data refresh and audit-log rollup** |
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-5 -->

Note F13's `EntitySnapshots` is described here as *"full prior-state JSONB"*, where the data
document describes it as a snapshot of the entity's key fields **at** the transition. Before vs
after is not a detail one can leave ambiguous in an audit table.
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-5 -->

### Integration and frontend {#f-integration}

| | Component | Phase 1 scope |
|---|---|---|
| F16 | Four adapter contracts — `IDcFeedAdapter`, `IAccountingExporter`, `IEdFiAdapter`, `ILicenseAdapter` — **keyed DI registration per state code**, implementations in `cnp_extensions.{state}.dll` resolved at startup | Contracts defined; **one stub `IDcFeedAdapter` returning canned data** |
| F17 | Frontend shell — Angular 17+, `@linq/snackpaq` with CSS-variable brand tokens, Angular Formly, Keycloak OIDC, LaunchDarkly SDK, URL pattern `/{programYear}/...` | Application list, application detail, audit timeline, one config-admin screen |
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-5 -->

F17 names **`@linq/snackpaq`** as the design system, with per-tenant branding through CSS
variables — which is the mechanism the delivered "Public Trust Modern" token set would ride on.
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-5 -->

## The six engines {#engines}

| | Engine | Phase scope |
|---|---|---|
| E1 | **Workflow Engine** — data-driven state machine, named hooks, IsFederal guardrails on every row | **Phase 1: built.** `SponsorApplication` entity type registered |
| E2 | **Rules Engine** — Microsoft Rules Engine on versioned, effective-dated JSONB. Categories FEDERAL_IMMUTABLE / FEDERAL_CONFIGURABLE / STATE_CONFIGURABLE / TENANT_CONFIGURABLE. **Federal math excluded by design — that lives in code** | Phase 1: scaffolded, minimal use for state-configurable application-validation rules. Full activation Phase 2 |
| E3 | **Form Engine** — year-versioned `FormDefinitions`; server emits `FormlyFieldConfig[]` | **Phase 1: built.** SNP application FormDefinition seeded; multi-step form renders end to end |
| E4 | Review Instrument Engine | Phase 2 |
| E5 | **Federal Report Engine** — plug-in `IFederalReportBuilder` per (ReportType, StateCode); orchestrator sequences ValidateAsync → ResolveSubmissionMode → BuildPart{A/B/C/C2} → AssembleAsync; reads Snowflake, writes a ReportPackage to S3 | Phase 2 (FNA-44 first); **Phase 1 scaffolds the contracts only** |
| E6 | VCA Instrument Engine | Phase 2 |
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-6 -->

## The Phase 1 vertical, step by step {#vertical}

The clearest end-to-end statement of what ships, with the foundation component exercised at
each step. Described as *"the thinnest possible slice that exercises every foundation component
end-to-end… deliberately narrow on features so that the foundation is built for real, not
stubbed."*

1. Sponsor hits the demo state's subdomain; YARP resolves the tenant and builds `ICnpContext`
   **[F5, F6]**
2. Redirect to Keycloak for OIDC login against the demo state's IdP **[F7]**
3. On callback the JWT (roles + tenant scope) is held **in service memory**;
   `ICnpPermissionService` gates every UI element **[F8]**
4. Application list — a server-driven query of `cnp_ops.{demo-state}` scoped to this sponsor
   **[F2, F8]**
5. "Create new application" → the Form Engine returns the SNP `FormDefinition` as
   `FormlyFieldConfig[]`; the multi-step form renders **[E3]**
6. Save drafts, then submit → a workflow transition Draft → Submitted, which writes an audit row
   **[F13]** and emits a notification **[F14]**
7. State caseworker logs in — **same Keycloak realm, different role.** Approve is gated by
   `ICnpPermissionService` **[F8]**
8. Caseworker either returns for correction (a `ReturnedForCorrection` transition **with
   comments**) or approves
9. On approval the engine runs the `NoNDLMatch` federal pre-condition hook, which calls the NDL
   adapter **[F16]**. **A canned ConfirmedMatch blocks the approval**, an audit row is written,
   and the caseworker sees a federal-block notification
10. On a clean approval, `FreezeClaimLaws` snapshots the active rates and rules from
    `cnp_global` into a `ClaimLaws` row in `cnp_ops`
11. A LINQ administrator changes the application-deadline CnpDefault; `ICnpConfigService`
    applies the `IsFederal` check, invalidates the Immediate-tier Redis cache, and writes to
    `FieldChangeLog`. **Within 10 minutes the sponsor's UI reflects the new deadline** — the
    speed demo
12. Anyone with `Audit.View` opens the Audit Timeline and reconstructs the full history from
    `EntitySnapshots` and `FieldChangeLog`
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-8 -->

### What actually gets written {#code-scope}

| Area | Deliverable |
|---|---|
| Domain (SNP) | `SponsorApplication` entity + repository; SNP FormDefinition seed; `NoNDLMatch` hook; SNP workflow definition seed; SNP RolePermission seeds; demo-state synthetic data |
| Frontend | Application list, application detail (Formly-rendered), **audit timeline panel**, **config admin screen**, tenant-branding pipeline, OIDC bootstrap, route guards, layout shell |
| Integration | **Stub NDL adapter** returning canned ConfirmedMatch / PossibleMatch / NoMatch. No DC adapters, no accounting exporters |
| Tests | **Characterization tests against the legacy SNP application-approval stored procedure (≥ 80% branch coverage)**; **Playwright E2E** covering the functional requirements; xUnit on every Layer-1 service |
| Infrastructure | **Terraform** for the Phase-1 environment set (Dev, Staging, Demo, UAT, **per-PR ephemeral**); GitHub Actions; **AWS CodeDeploy**; ECS Fargate services |
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-8 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-9 -->

Terraform, AWS CodeDeploy, Playwright and xUnit are named **only here.** So is the NDL adapter
being routed through the `IDcFeedAdapter`-style adapter layer **[F16]** rather than being a
direct service call.

## Foundation build order {#build-order}

Mapped onto sprint windows. Note this uses the **feature-list numbering** (Mobilization, Sprint
1–6, Hardening), not the prototype plan's Sprint 1–8.

| Window | Foundation work |
|---|---|
| Mobilization (Wks 1–2) | F4 Snowflake account, F7 Keycloak install, F9 ISecretProvider, F17 frontend skeleton, F16 four contracts defined (no implementations), DevOps/observability bootstrap |
| Sprint 1 (Wks 3–4) | F1 `cnp_global` schema v1, F2 `cnp_ops` schema v1, F5 `ICnpContext`, F13 audit scaffolding, F11 IsFederal columns, F17 shell with OIDC login working |
| Sprint 2 (Wks 5–6) | F10 config service with three-layer resolution and IsFederal write-block, F12 LaunchDarkly, E1 workflow tables, F11 guardrail fully wired across Config + RBAC + Workflow |
| Sprint 3 (Wks 7–8) | E1 execution engine and named hooks, F8 permission service with three-layer override, F6 TenantRegistry row, `NoNDLMatch` hook (stub adapter) |
| Sprint 4 (Wks 9–10) | E3 Form Engine `FormlyFieldConfig` generator, **ClaimLaws table + FreezeClaimLaws action**, F14 notifications minimal, F15 Hangfire jobs |
| Sprints 5–6 (Wks 11–14) | F17 application list, detail, audit timeline, config admin. Speed-demo plumbing exercised end to end |
| Hardening (Wks 15–16) | Security review of every foundation interface; characterization-test baseline; performance baseline; **onboarding test** |
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-11 -->

## Foundation acceptance criteria {#acceptance}

Distinct from the prototype's demo-readiness list: these prove **the foundation** is built, and
are *"required for the platform to be ready for Phase 2 to begin without rework."*

1. **Tenant isolation** — verified by introducing a **second synthetic state**, provisioning a
   TenantRegistry row, and demonstrating one state's user cannot see the other's data **even
   via direct API call**
2. **Federal guardrail enforcement** — attempts to override an `IsFederal` CnpDefault, an
   `IsFederal` RolePermission and an `IsFederal` WorkflowTransition each block at write time,
   **return the same error shape, and audit-log identically**
3. **Configuration speed demo** — a change via the Config Admin UI reflected within ten minutes,
   with `FieldChangeLog` capturing actor / before / after / timestamp
4. **ClaimLaws freeze** — *"the active rates from `cnp_global.ClaimRateAmounts` are written into
   a `cnp_ops.ClaimLaws` row; subsequent reads show the snapshotted values even after the live
   rates change"*
5. **Audit completeness** — every state-changing event produces matching rows in all three
   tables, and a reviewer can reconstruct any application's full history **using only those
   three tables**
6. **Secrets contract** — no secret value in any repository file or environment variable;
   `ISecretProvider.Get(path)` the only access pattern; **the offshore principal demonstrably
   cannot access production paths**
7. **Adapter contracts** — all four defined and resolvable via keyed DI; one stub proves the
   registration pattern
8. **Migration runner** — a **second synthetic state provisioned end to end** (cnp_ops cluster +
   schema + seed data + TenantRegistry row + Keycloak realm) by running the migration runner
   only, **with no application code change**
9. **Frontend shell** — a second synthetic state's subdomain renders with that state's brand
   tokens, OIDC realm and feature-flag set, **without a frontend code change**
10. **Definition of Done** — *"the LINQ configuration team can re-execute the prototype outcome
    on a different demo state without a single new line of code."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-11 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-12 -->

**Three of these (1, 8, 9) require provisioning a second state inside Phase 1**, and criterion
10 makes doing so on an arbitrary state the Definition of Done. No other document in the corpus
schedules or estimates that work, and the prototype plan states the opposite constraint — *"one
state only. No multi-state scenarios, no cross-state features."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-11 -->

## What Phase 2 and 3 plug in without touching the foundation {#future-phases}

**Phase 2:** six more program domains (each is FormDefinition rows, workflow rows, RolePermission
rows and per-program hooks — *"zero foundation change"*); the Claims domain as a new
`WorkflowEntityType` the engine runs unchanged; the Federal Report Engine; DC feed adapters
(Indiana, Hawaii); accounting exporters; the AI layer (reading Snowflake, writing through
existing approval gates); the full admin UI; multi-region (*"Terraform modules already designed
for multi-region"*); and new states — each *"a TenantRegistry row, a Keycloak realm, a cnp_ops
Aurora cluster, CnpDefault overrides, and the four adapter implementations. **No code deploy.**"*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-10 -->

**Phase 3:** Food Distribution as `cnp_ext` schemas plus a domain module; CACFP IMP rule
activation as a pure data/configuration change (RuleCategory promotion plus a
`Cacfp.ImpRulesEnabled` flag); and offline review checkout, either as a PWA capability or a
`ReviewCheckout` API with a companion app — *"architecture decision made during Phase 2."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-10 -->

## Documents this one references that are not in the corpus {#missing-refs}

- **The Synopsis** — which *"names it as five blocks (Platform Foundation, Engines, Configuration
  & Access, Integrations, Operations & Safety)"*
- **The v0.2 proposal**, whose Section 5.3 defines the onboarding test used as a Hardening
  deliverable
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-12 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-11 -->

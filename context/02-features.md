<!-- PROJECT CONTEXT — synthesised, not a source document.

     Every factual claim here needs a provenance comment naming where it came from:
         <!-- from: knowledge/distilled/<topic>.md#<anchor> -->
     `python scripts/project-context.py check` fails on a claim without one.

     If a statement has no source, it is an ASSUMPTION. Move it to 06-open-questions.md
     with the assumption stated, rather than leaving it here where the next reader will
     take it for a requirement. -->

# Features

51 refined features (RF-01–RF-51) across nine capability areas, **2,264 hours total**, mapped
to eight business functions (FRD-01–FRD-08).
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#effort -->

Sprint labels below are the **week** ranges, not sprint numbers — the feature list and the
sprint plan number their sprints differently and are offset by one.
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#shape -->

## Feature inventory {#inventory}

### Week 0 blockers {#week-0}

| ID | Feature | Effort | Why it blocks |
|---|---|---|---|
| RF-48 | AWS foundation: Aurora ×2, ECS, ElastiCache Redis, Secrets Manager, GitHub CI/CD | 72h | *"nothing else starts before this"* |
| RF-50 | Synthetic data only in every environment offshore can touch; the pipeline must exist first | 56h | Gates offshore work beginning at all |
| RF-05 | Close the identity provider decision | 16h | Affects ECS provisioning and Secrets Manager paths, not just login |
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#week-0 -->

### Mobilization — Weeks 1–2 {#mob}

| ID | Area | Feature | Effort |
|---|---|---|---|
| RF-44 | Data & Architecture | Schema evolution is migration-managed; hardcoded year constants and versioned parallel schemas prohibited | 32h |
| RF-47 | Data & Architecture | Single `ISecretProvider` fronting AWS Secrets Manager; path scheme `cnp/{env}/{tenant\|global}/{category}/{name}`; no plaintext in config | 48h |
| RF-49 | DevOps | Environment posture; all deploys tag-based; us-east-1 only | 40h |
| RF-51 | DevOps | Configuration specialist signs off the demo environment before the demonstration | 16h |
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#effort -->

### Weeks 3–4 — identity and foundations {#weeks-3-4}

| ID | Area | Feature | Effort |
|---|---|---|---|
| RF-01 | Security & Auth | Real OIDC login against the demo-state realm; **no mock tokens anywhere in the flow** | 60h |
| RF-02 | Security & Auth | Subdomain-driven tenant resolution: subdomain → YARP → realm → `ICnpContext` selecting cnp_global + the state's cnp_ops | 48h |
| RF-03 | Security & Auth | JWTs carry roles + tenant scopes only, **never raw permissions**; held in service memory, never localStorage | 20h |
| RF-04 | Security & Auth | SSO via an OIDC broker, extensible to all states; Phase 1 wires one realm | 32h |
| RF-41 | Data | Two Aurora databases: cnp_global shared + one cnp_ops; the database boundary is the tenant boundary | 64h |
| RF-45 | Data | .NET 8 + MediatR, net-new build, **no copy-paste from legacy CTS/DIS** | 64h |
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#effort -->

### Weeks 5–6 — the engines {#weeks-5-6}

| ID | Area | Feature | Effort |
|---|---|---|---|
| RF-18 | Workflow | **Thin, data-driven workflow executor** — all states, transitions, guards and side-effects as rows in 5 cnp_global tables | **100h (XL)** |
| RF-19 | Workflow | Conditions and actions resolve to named hooks registered per entity type and resolved by DI; the engine never calls business code directly | 56h |
| RF-20 | Workflow | Every workflow row carries `IsFederal`; federal rows guardrailed at INSERT | 40h |
| RF-21 | Workflow | Tenant customisation expressed **only** via `TenantTransitionOverrides` — never state-keyed branches in code | 32h |
| RF-22 | Workflow | Every executed transition writes audit rows (who, when, from/to, condition and action outcomes) | 28h |
| RF-30 | Config | Three-layer resolution: Platform Default → Program Override → Tenant Override, most-specific-wins | 64h |
| RF-31 | Config | Every key typed, bounded and effective-dated; every override needs Effective Date + Justification | 56h |
| RF-32 | Config | `IsFederal = true` blocks tenant overrides at write time; no endpoint may override a federal-locked value | 28h |
| RF-33 | Config | `ICnpConfigService.GetValue<T>()` is the **sole** accessor; direct config-table reads prohibited | 36h |
| RF-36 | Config | ~5 module-level LaunchDarkly flags wired end-to-end, including frontend route guards | 32h |
| RF-06 | Security | Role-based authorisation with 3 override layers; **explicit Revoke beats any lower Grant** | 72h |
| RF-07 | Security | All authorisation flows through `ICnpPermissionService`; direct role checks prohibited | 40h |
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#effort -->

### Weeks 7–8 — federal controls {#weeks-7-8}

| ID | Area | Feature | Effort |
|---|---|---|---|
| RF-08 | Security | `IsFederal` permissions are irrevocable by any override layer | 24h |
| RF-09 | Security | `UserRoleAssignments` carry `ScopeType`, enforced automatically at the repository layer (replaces ~5,082 legacy ACL rows) | 64h |
| RF-10 | Security | Deliver the SECURITY permission domain + the five demo roles | 32h |
| RF-23 | Federal | `NoNDLMatch` federal pre-condition hook on `ApproveApplication`, checking org name, EIN and named principals | 48h |
| RF-24 | Federal | **ConfirmedMatch is an absolute, non-overridable block** — no user, admin or config can bypass | 24h |
| RF-25 | Federal | PossibleMatch routes to `NdlOverrideRequests` for human review rather than blocking outright | 32h |
| RF-26 | Federal | The NDL source may be a stub, but **blocking behaviour and audit records are real** | 28h |
| RF-27 | Federal | On approval, `FreezeClaimLaws` writes an immutable ClaimLaws record | 56h |
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#effort -->

### Weeks 9–10 — the application domain {#weeks-9-10}

| ID | Area | Feature | Effort |
|---|---|---|---|
| RF-11 | Applications | Sponsor views a sponsor-scoped list, opens detail, completes and submits the SNP annual application | 64h |
| RF-12 | Applications | Detail renders workflow action buttons **dynamically** — only transitions valid for state, role and permissions are shown | 40h |
| RF-13 | Applications | Caseworker reviews and either advances or returns with corrections required | 40h |
| RF-14 | Applications | Approval fires federal pre-condition checks and configured side-effects | 36h |
| RF-15 | Applications | SNP lifecycle seeded as workflow config: Draft → Submitted → Under Review → (Returned) → Approved, Denied terminal | 32h |
| RF-16 | Applications | Submission validation failures recorded and visible to the sponsor, with state-side override where config permits | 32h |
| RF-17 | Applications | **Server-defined application form** (FormDefinition metadata → server-built field config); the client never hardcodes structure | 56h |
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#effort -->

### Weeks 11–12 — freeze display, config admin, audit {#weeks-11-12}

| ID | Area | Feature | Effort |
|---|---|---|---|
| RF-28 | Federal | The ClaimLaws freeze is visible in the UI after approval | 24h |
| RF-29 | Federal | **One generic freeze mechanism serves all programs** via configuration — eliminates legacy per-program duplicated procedures | 32h |
| RF-34 | Config | Config Admin screen: an authorised user changes a tenant-level setting, observably live **in under 10 minutes** | 60h |
| RF-35 | Config | Every configuration write is logged to `FieldChangeLog` | 24h |
| RF-37 | Audit | Append-only audit layer with **100% capture of the demo flow** | 56h |
| RF-38 | Audit | Audit records capture actor, timestamp, entity, action and before/after content (entity snapshots as JSONB) | 56h |
| RF-39 | Audit | One audit timeline screen presenting an application history end to end, **human-readably** | 48h |
| RF-40 | Audit | Audit data is immutable — **no update or delete paths** | 20h |
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#effort -->

### Weeks 13–14 — hardening {#weeks-13-14}

| ID | Area | Feature | Effort |
|---|---|---|---|
| RF-42 | Data | Build only what the flow needs: ~20–30 cnp_global and ~60–80 cnp_ops tables; other domains ship as **empty migration stubs** | 72h |
| RF-43 | Data | Data spine ProgramGroups → ProgramGroupYears → ProgramGroupEnrollments; entities FK-chain through ProgramGroupYears | 48h |
| RF-46 | Data | Frontend: Angular 17+ SPA, net-new repo, reusing `@linq/snackpaq` + Angular Formly; program-year-scoped URLs | 64h |
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#effort -->

## Dependencies between features {#dependencies}

| Must ship first | Before | Why |
|---|---|---|
| RF-48 (AWS foundation) | Everything | *"nothing else starts before this"* |
| RF-50 (synthetic data pipeline) | Any offshore work | A Week-0 gate; offshore cannot touch an environment without it |
| RF-05 (IdP decision) | RF-01, RF-02, RF-04, and ECS/Secrets provisioning | The choice determines paths and task definitions, not just login |
| RF-41 (the two databases) | RF-30, RF-18, everything operational | The tenancy boundary is the schema |
| RF-18 (workflow executor) | RF-12, RF-13, RF-14, RF-23, RF-27 | Every application action is a transition |
| RF-19 (named hook registry) | RF-23 (NoNDLMatch), RF-27 (FreezeClaimLaws) | Both are hooks |
| RF-20 + RF-32 (IsFederal guardrails at INSERT) | Any seed data load | Triggers must be deployed and tested *before* seeds run |
| RF-30/31/33 (config engine) | RF-17 (server-defined form), RF-34 (Config Admin) | The form definition and the speed demo both read config |
| RF-06/07 (authorisation) | RF-11, RF-12 | Action buttons are role-filtered server-side |
| RF-37/38 (audit layer) | RF-14, RF-27 | Approval must write audit rows in the same transaction |
| **API contracts frozen (end of Weeks 7–8)** | RF-46 and all frontend work | *"They must not change after Sprint 4 ends"* |
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#week-0 -->
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#sprint-4 -->
<!-- from: knowledge/distilled/02-workflow-engine.md#named-hooks -->
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#layers -->

Two dependencies are **people, not code**, and both are named as pre-sprint requirements:

- The **demo-state hook** must be identified by the onshore config specialist before Weeks 5–6.
  If it is not, that sprint proceeds without it and it lands in Weeks 7–8 — explicitly
  acceptable.
- The **speed-demo config key** must be identified before Weeks 11–12, and must be visible in
  the workflow, Tier 1 or Tier 2 cached, and **not** `IsFederal`.
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#sprint-3 -->
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#sprint-6 -->

## Features mentioned but not specified {#underspecified}

Named somewhere with no detail behind them. **These are not backlog items yet**, and recording
them here stops them being estimated as though they were.

| Item | Where it appears | What is missing |
|---|---|---|
| **Site applications** | 4 of 6 screens; `SiteApp` is a workflow entity type | No requirement, no API contract, no effort estimate. Possibly out of Phase 1 entirely |
| **Supporting document upload** | Screens, and the federally-locked document gate | FRD-03 lists it out of scope *"unless explicitly configured in scope for the demo"* |
| **Application sections 2–7** | Screen 4's rail names them | Only section 1 has a field inventory. RF-17 requires all of them as server metadata |
| **The Returned state** | RF-15, FRD-04, the UI | Omitted from the prototype's demo-state seed |
| **Withdrawn and Closed states** | The UI and the design system | No requirement mentions them |
| **Application versioning** | Screen 3 shows "Version 1" | No version model anywhere |
| **Bulk site actions** | Screen 6 has checkboxes and select-all | No bulk action bar; nothing says what selection enables |
| **Import Sites** | Screen 6 header action | No file format, validation or partial-failure handling |
| **Validation results view** | Linked from three screens | Never designed |
| **Audit timeline screen (RF-39)** | 48h estimated | Not in the screen handover; "human-readable" is the only specification |
| **Config Admin screen (RF-34)** | 60h estimated | Not in the screen handover |
| **The 7 IsFederal guardrail assertions** | A demo-readiness gate | Named as seven; enumerated nowhere |
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screens-5-6 -->
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-4 -->
<!-- from: knowledge/distilled/11-screens-and-design-system.md#status-vocabulary -->
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#effort -->
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#dod-demo -->

## Traceability that cannot currently be reconstructed {#traceability-gap}

The FRD set was derived from a test plan defining **13 test suites (TS-01–TS-13)** and an
execution workbook defining **83 scenarios (SC-101–SC-1303)** with full RF → suite → scenario
mapping. Every FRD cross-references those suites; **neither document was supplied.** The QA
engineers therefore have no scenario catalog, and RF → test traceability cannot be rebuilt from
this handover.
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#missing-documents -->

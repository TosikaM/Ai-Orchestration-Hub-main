# Delivery plan, gates and team

## Shape {#shape}

**16 weeks from kickoff to demo-ready** — August to early December — split as **14 weeks of
active build plus 2 weeks of freeze and demo prep**. The nTIG window is external and fixed.
<!-- source: CSN-Prototype-140826-133159.md#page-1 -->
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->

Sprint velocity assumes 2 offshore backend engineers + 1 offshore frontend + 1 offshore QA,
with onshore oversight.
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->

> The 51-feature list uses a different sprint labelling (Mob, S1–S5, H over 14 weeks) that is
> offset by one from the sprint plan's Sprint 1–8 over 16 weeks. See
> `99-contradictions-and-open-questions.md#sprint-numbering`.

## The eight sprints and their exit gates {#sprints}

Each gate is a hard stop, not a status update.

### Sprint 1 — Infrastructure & Environments · Weeks 1–2 · Aug 17–28 {#sprint-1}

AWS dev/staging with VPC, subnets, security groups · Aurora cluster live · ElastiCache Redis ·
ECS Fargate with placeholder task definitions · Secrets Manager paths established and
documented · GitHub Actions build/test/deploy plus the **IsFederal guardrail check** ·
`.github/CODEOWNERS` with branch protection · identity provider deployed to staging (admin
console onshore-only) · synthetic data generation script runnable in one command · offshore
individual accounts for dev only · LaunchDarkly project.

> **Gate — the offshore kickoff gate.** Before the offshore team receives anything: (1) the
> GitHub repo exists and is isolated from all existing LINQ repositories, (2) the dev AWS
> account has **no VPC peering or connectivity to any existing LINQ account**, (3) offshore
> individuals have named accounts, not shared credentials, (4) the design document package is
> exported and delivered. Onshore tech lead **and** DevOps both sign off.
<!-- source: CSN-Prototype-140826-133159.md#page-9 -->
<!-- source: CSN-Prototype-140826-133159.md#page-10 -->
<!-- source: LINQ CNP - Prototype  Jenny Track - Sprint Plan.md#sprint-1 -->

### Sprint 2 — Database Schema & Platform Services · Weeks 3–4 {#sprint-2}

`cnp_global` migrations (LookupCodes, FederalProgramDefinitions, PovertyGuidelineHistory,
ConfigDefinitions, the five workflow tables, PermissionCatalog, RoleDefinitions,
RolePermissions) · `cnp_ops.{demo_state}` schema created and confirmed isolated · **both
IsFederal triggers deployed and tested** · the three database roles created · ConfigDefinitions
seeded (~20 keys covering application workflow) · PovertyGuidelineHistory seeded with current
SY rates (public FNS data).

Platform services: .NET 8 API scaffold with MediatR, FluentValidation and exception middleware
· MediatR folder structure established · **DTO pattern enforced** · `ICnpConfigService`
three-layer resolution (no Redis yet) · `ICnpPermissionService` · JWT validation middleware ·
tenant context middleware setting `search_path` per request · healthcheck endpoint · IdP realm
configured with test users.

> **Gate:** the onshore tech lead verifies (1) IsFederal triggers reject a test write to a
> federal-locked key, (2) tenant context middleware correctly sets schema per JWT claim, (3)
> **the offshore team cannot connect to staging from their dev environment.** All three must
> pass.
<!-- source: CSN-Prototype-140826-133159.md#page-10 -->
<!-- source: CSN-Prototype-140826-133159.md#page-11 -->

### Sprint 3 — Workflow Engine & Named Hooks · Weeks 5–6 {#sprint-3}

`WorkflowEngine` service · named hook registry with `IWorkflowCondition` / `IWorkflowAction`
interfaces, DI registration and a catalog endpoint · four hooks (`FreezeClaimLaws`
IsFederal=true, `AllClaimErrorsResolved`, `NoNDLMatch` IsFederal=true as a stub returning true,
and the demo-state hook) · demo state workflow seeded · **the demo-state customization applied
via `TenantTransitionOverrides`, not by modifying the base workflow** · unit tests with 100%
coverage of condition/action logic.

Pre-sprint requirement: the demo-state hook identified by the onshore config specialist before
Sprint 3 starts — and if not identified, **Sprint 3 proceeds without it and it is added in
Sprint 4. This is explicitly acceptable.**

> **Gate:** guardrail assertion tests pass — (1) `FreezeClaimLaws` cannot be removed from the
> `ApproveApplication` transition via API, (2) a direct DB attempt to delete a federal
> condition raises a PostgreSQL exception, (3) **the exception is logged to `AuditLogs`.**
> Onshore tech lead signs off before Sprint 4 begins.
<!-- source: CSN-Prototype-140826-133159.md#page-11 -->
<!-- source: CSN-Prototype-140826-133159.md#page-12 -->

### Sprint 4 — Application Domain · Weeks 7–8 {#sprint-4}

Applications tables · **AuditLogs, EntitySnapshots, FieldChangeLog** · ClaimLaws table ·
application commands and queries · every command writes to AuditLogs + EntitySnapshots, every
field change to FieldChangeLog · ClaimLaws row created by the `FreezeClaimLaws` hook, verified
by integration test · 30–50 synthetic applications.

API contracts finalized this sprint and **frozen** — the frontend builds against them from
Sprint 5 and they must not change:

```
GET  /applications?status=&page=&pageSize=
POST /applications
GET  /applications/{id}
POST /applications/{id}/transitions      body: { "toState": "Submitted" }
GET  /applications/{id}/audit
GET  /applications/{id}/claim-laws
```

> **Gate:** the integration test passes the full lifecycle Submit → UnderReview → Approved;
> a ClaimLaws row exists in the DB post-approval; AuditLogs and EntitySnapshots rows exist for
> every transition; API contracts published and frozen. Also: **ClaimLaws rows have no UPDATE
> endpoint — an attempt returns HTTP 405.**
<!-- source: CSN-Prototype-140826-133159.md#page-12 -->
<!-- source: CSN-Prototype-140826-133159.md#page-13 -->

### Sprint 5 — Frontend shell, auth, application list · Weeks 9–10 {#sprint-5}

Angular 17+ with the design system · OIDC login storing the token **in memory, not
localStorage** · route guards · role-based navigation (Caseworker sees Applications; Reviewer
sees Applications + Review Queue; LINQConfigAdmin sees Config Admin, hidden from other roles)
· application list with paging, status filter and sponsor search · loading, error and empty
states all handled, **no console errors visible in the demo** · responsive layout.

HTTP interceptors attach the Bearer token and handle 401 (redirect to login) and 403 (show
access-denied). Angular environment files contain the API base URL only — no credentials.

> **Gate:** full login → application list works end-to-end in staging for Caseworker, Reviewer
> and LINQConfigAdmin. **Verify 403 if a Caseworker hits a Reviewer-only endpoint directly —
> not just hidden in the UI.**
<!-- source: CSN-Prototype-140826-133159.md#page-13 -->
<!-- source: CSN-Prototype-140826-133159.md#page-14 -->

### Sprint 6 — Frontend workflow, audit trail, speed-demo screen · Weeks 11–12 {#sprint-6}

Application detail page with status badge and dynamically-driven action buttons — **unavailable
actions hidden, not disabled** · approval screen showing the ClaimLaws summary · **collapsible
audit trail panel formatted for a human, not a developer** · the demo-state customization
visible in the UI · Redis integrated into `ICnpConfigService` with the three cache tiers ·
cache-bust endpoint live · **Config Admin screen** (LINQConfigAdmin only) — a single config key
editor that calls cache-bust on save and confirms propagation. *"Used for speed demo — must be
polished."*

> **Gate — the speed demo dry run.** Onshore tech lead + config specialist run the full flow:
> change made in Config Admin → visible in the application workflow **within 5 minutes** →
> audit log shows the cache-bust event → the full sequence is timed. **If over 8 minutes,
> investigate before Sprint 7.**
<!-- source: CSN-Prototype-140826-133159.md#page-14 -->
<!-- source: CSN-Prototype-140826-133159.md#page-15 -->

The speed-demo config key must be identified before Sprint 6 and must satisfy three
constraints: **visible in the application workflow** (the state contact must recognise the
change), **Tier 1 or Tier 2 cache** (propagates in minutes, not at midnight), and **not
`IsFederal = true`** — *"the demo shows flexibility, not a block."* Candidate keys: an
application submission deadline threshold, a notification subject line, a validation message,
a display label. The onshore config specialist also documents the **"legacy equivalent" story**
— how long this change would take on the current system.
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->
<!-- source: CSN-Prototype-140826-133159.md#page-14 -->

### Sprint 7 — Demo state UAT & data validation · Weeks 13–14 {#sprint-7}

UAT environment from the Sprint 6 tag · curated dataset of 50–100 applications matching the
demo state's real program profile · **informal UAT with 2–3 people from the demo state agency**,
a 2-hour session facilitated by the LINQ account team · issue log triaged (fix before demo /
fix post-demo / won't fix) · high-priority fixes · 10–20 applications run through the full
lifecycle against documented expected results · internal dry-run demo timed at ≤30 minutes ·
IsFederal guardrail regression suite passing.

What to watch for in UAT: any step where the state contact says *"that's not how we do it"* —
investigate whether it is a missing customization, a config gap or a design difference.
Performance: application list under 2 seconds, detail under 1 second. **Zero tolerance for
visible or console errors.** Terminology: does everything use the state's preferred language?

Explicitly **not** in this sprint: new features, claims workflow, FNS report work. *"This is a
fix sprint only."*

> **Gate:** demo state contact confirms UAT satisfactory; the internal dry run completes in
> ≤30 minutes with no technical failures; high-priority issues closed; guardrail suite passing;
> onshore tech lead approves tagging the demo release.
<!-- source: CSN-Prototype-140826-133159.md#page-15 -->
<!-- source: CSN-Prototype-140826-133159.md#page-16 -->

Note the boundary drawn on validation scope: *"Full replay against real CTS/DIS data is
onshore-only work done during state migration — not part of the greenfield prototype."*
<!-- source: CSN-Prototype-140826-133159.md#page-15 -->

### Sprint 8 — Demo environment freeze & final prep · Weeks 15–16 {#sprint-8}

Demo deployed from the approved Sprint 7 tag, **freeze enforced, no code changes after
deploy** · smoke test **run by someone who has not seen the demo before**, confirming it works
without coaching · performance validation measured on the demo environment, not staging ·
final data check (no placeholder names like "Test Sponsor 1") · **documented fallback plan**
(staging on an identical tag) · account team briefed on the script, Q&A, and what to escalate
versus answer · invite list confirmed.

**No new features in Sprint 8 regardless of what is requested.** The offshore team works only
on the post-prototype backlog; **no offshore changes to the demo environment — the freeze is
absolute.**

> **Gate:** smoke test passes with an unfamiliar operator; performance benchmarks met; the demo
> environment is stable; the onshore tech lead formally declares "demo-ready"; the first state
> demo is scheduled.
<!-- source: CSN-Prototype-140826-133159.md#page-16 -->
<!-- source: CSN-Prototype-140826-133159.md#page-17 -->

## Definition of Done {#dod}

### Per story {#dod-story}

Code compiles without warnings · unit tests written and passing · integration test covers the
happy path **and at least one failure path** · no new console errors in staging · API contract
matches the frozen contract for that sprint · **if compliance-related, onshore tech lead has
reviewed and approved the PR** · deployed to staging and smoke tested.
<!-- source: CSN-Prototype-140826-133159.md#page-17 -->

### For the prototype to be demo-ready {#dod-demo}

| Requirement | Verification |
|---|---|
| Login works for demo Caseworker, Reviewer and LINQConfigAdmin | Manual smoke test |
| Application list loads with realistic synthetic data in <2 seconds | Stopwatch on the demo environment |
| Full workflow Submit → UnderReview → Approve completes without error | E2E integration test + manual |
| Demo state-specific hook fires correctly | Automated integration test **+ visible in the audit trail** |
| ClaimLaws displayed on the approval screen with correct rates | Manual verification against the seeded rates |
| Audit trail shows all transitions with actor, timestamp, state change | Manual in UI + DB query |
| Config change propagates to the workflow in <5 minutes | Timed during the dry run |
| Role switch shows different navigation **and different data access** | Manual smoke test on both roles |
| Caseworker cannot reach a Reviewer-only endpoint by direct API call | Automated: HTTP 403 |
| **All 7 IsFederal guardrail assertions passing** | Automated, CI/CD |
| No real state data in the demo environment | Data review by the onshore config specialist |
| Demo environment stable for 48 hours | ECS task restart count = 0 over 48 hours |
<!-- source: CSN-Prototype-140826-133159.md#page-17 -->
<!-- source: CSN-Prototype-140826-133159.md#page-18 -->

Performance targets for the freeze sprint: application list <2s, application detail <1s,
approval transition <3s, config propagation <5min — **all measured from the demo environment,
not staging.**
<!-- source: CSN-Prototype-140826-133159.md#page-16 -->

## Branch protection rules {#pr-rules}

Enforced in GitHub, described as *"not optional"*:

- Any file in `/src/Hooks/`, `/src/Compliance/`, `/src/Audit/` or `/migrations/` → **onshore
  tech lead required as approver**
- Any PR modifying `ConfigDefinitions` or `WorkflowTransitionConditions` seed data → onshore
  tech lead required
- Any PR adding a new `IsFederal=true` row must include a corresponding guardrail assertion
  test **in the same PR**, enforced by a required status check that scans the diff
- **Offshore engineers cannot self-approve any PR**
- The CODEOWNERS file is itself a protected path
<!-- source: CSN-Prototype-140826-133159.md#page-6 -->

## The delivery team {#team}

Algoworks, 13 people:

| Name | Role |
|---|---|
| Sourav Ghosh | Project Manager |
| Tosika Mukherjee | Solution / Technical Architect |
| Atul Matvar | Data Engineer |
| Suraj Singh | DevSecOps & Platform Lead |
| Robin Kumar | Backend Engineer 1 |
| Vinoth K | Backend Engineer 2 |
| Ashish Nigam | Backend Engineer 3 |
| Ashutosh Singh | Frontend Engineer (UI/UX) 1 |
| Umang Gupta | Frontend Engineer (UI/UX) 2 |
| Pratibha Tanwar | QA Engineer 1 |
| Abhilash Soni | QA Engineer 2 |
| Reshmi Parvin | Junior AI 1 |
| Sairajendra Jagdale | Junior AI 2 |
<!-- source: CSN-Prototype-140826-133159.md#page-5 -->

Onshore counterpart roles named across the plan: Onshore Technical Lead (approves sensitive
changes, all named hooks, all federal seed data, and every demo deploy), Onshore Configuration
Specialist (identifies the demo-state hook and the speed-demo key; signs off the demo
environment), DevOps/Platform (AWS provisioning), and the LINQ account team (facilitates UAT
and the demo).
<!-- source: 08_FRD_Delivery_Foundation.md#section-2 -->
<!-- source: CSN-Prototype-140826-133159.md#page-9 -->

## The 51 features by effort {#effort}

**2,264 hours total** across 51 refined features (RF-01–RF-51) in nine capability areas.
<!-- source: 51 Feature List.md#feature-detail -->

Largest single items: RF-18 the data-driven workflow executor (XL, 100h) · RF-48 AWS foundation
(L, 72h) · RF-42 build only what the flow needs, ~20–30 cnp_global and ~60–80 cnp_ops tables
with other domains as empty migration stubs (L, 72h) · RF-06 role-based authorisation with
three override layers (L, 72h) · RF-30 three-layer configuration resolution (L, 64h) · RF-41
the two Aurora databases (L, 64h) · RF-45 the .NET 8 + MediatR backend (L, 64h) · RF-09
ScopeType at the repository layer (L, 64h) · RF-11 the sponsor application flow (L, 64h) ·
RF-46 the Angular 17+ SPA (L, 64h).
<!-- source: 51 Feature List.md#feature-detail -->

Capability areas: Security & Auth · Data & Architecture · DevOps / Environments · Workflow
Engine · Configuration Engine · Federal Controls · Applications · Audit · (Config Admin).
<!-- source: 51 Feature List.md#feature-detail -->

## Named Week-0 blockers {#week-0}

- **RF-48** — the AWS foundation: *"nothing else starts before this"*
- **RF-50** — the synthetic-data pipeline *"must exist before offshore work begins"*
- **RF-05** — close the identity provider decision *"in Week 0 before build starts"*
<!-- source: 51 Feature List.md#feature-detail -->

## Synthetic data specification {#synthetic-data}

5–10 fake sponsors with realistic names and addresses in the demo state · 20–40 sites per
sponsor with realistic enrollment · applications across Draft, Submitted, UnderReview, Approved
and Declined, *"enough to make the list view look real"* · 3 Caseworker, 2 Reviewer, 1
StateAgencyAdmin, 1 LINQConfigAdmin accounts · demo state CnpDefaults seeded through the
three-layer hierarchy · **current-SY reimbursement rates using real published FNS data, because
they are public.**
<!-- source: CSN-Prototype-140826-133159.md#page-7 -->
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->

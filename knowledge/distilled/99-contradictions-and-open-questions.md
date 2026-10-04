# Contradictions and open questions

Every item here is a place where the source documents disagree with each other, or leave a
build-affecting value unstated. **Nothing here is resolved.** The corpus states its own rule
twice — *"where this document and a customer design document conflict, the design document
wins. Flag conflicts; don't silently resolve them"* — so resolving these by picking a
plausible default would be the specific failure the client warned against.
<!-- source: 00_FRD_Index.md#section-1 -->
<!-- source: CSN-Prototype-140826-133159.md#page-18 -->

Severity is about **what breaks if we guess wrong**, not about how hard the question is.

---

## BLOCKERS — a wrong guess produces rework, not a defect

### B1. Does `ClaimLaws` store dollar rates? {#claimlaws-rates}


⚠️ **Conflict** (blocker) — unresolved. Do not pick a default.
**The single most consequential contradiction in the corpus.** It determines the `ClaimLaws`
table schema, the signature of the claim calculation service, and whether a rate correction
can retroactively alter an approved claim.

*Says rates are NOT stored:*

- *"Dollar rates are not stored in ClaimLaws, they are resolved at claim calculation time from
  `ClaimRateAmounts` using the claim date as the effective date key."*
<!-- source: CSN-Data-140826-132933.md#page-4 -->
- *"Dollar amounts are not stored in ClaimLaws… The dollar amounts that correspond to that tier
  for any given claim month are looked up separately at compute time."*
<!-- source: CSN-The Math-140826-133113.md#page-2 -->
<!-- source: CSN-The Math-140826-133113.md#page-3 -->
- The `FreezeClaimLaws` hook description: *"Dollar amounts are NOT captured here — they resolve
  from ProgramMealRates at claim compute time."*
<!-- source: CSN-Workflow Engine-140826-132724.md#page-12 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-13 -->

*Says rates ARE stored:*

- Header line: *"ClaimLaws: rates frozen at application approval. A revised claim in December
  uses the rate frozen in October — not the new July rate."*
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-1 -->
- The overlay diagram shows `ClaimLawsId: 8821` carrying `LunFrRte: 4.12`, `PbrRte: 0.09`,
  `BrkFrRte: 2.27`, *"…all rates frozen."*
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-5 -->
- **The reference C# implementation reads rates directly off the ClaimLaws object** —
  `laws.SnlFrRte`, `laws.LunFrRte`, `laws.PbrRte`, `laws.BrkFrRte`, `laws.StateMatchRte` —
  under a comment stating *"the key insight: rates come from ClaimLaws (frozen), not live
  tables"*, and adds *"State-specific overrides (state match, severe need eligibility, SSO
  rates) live in ClaimLaws."*
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-8 -->
- The worked example: *"`ClaimLaws.FreezeOnApproval()` read the ProgramMealRates rows for NSLP
  SY2025-26 and stored them into a ClaimLaws record."*
<!-- source: CSN-Data-140826-132933.md#page-11 -->

**New evidence (30 June 2026 — the most recent document in the corpus).** The Foundational
Architecture makes "rates are stored" a **foundation acceptance criterion**, twice:

- *"On a clean approval, the `FreezeClaimLaws` action snapshots the active rates and rules from
  `cnp_global` into a `ClaimLaws` row in `cnp_ops`."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-8 -->
- Acceptance criterion 4: *"on application approval, the active rates from
  `cnp_global.ClaimRateAmounts` are written into a `cnp_ops.ClaimLaws` row; subsequent reads of
  the application show the snapshotted values even after the live rates change."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-11 -->

That is now **three sources on the "rates stored" side, including the reference implementation
and a testable acceptance criterion**, against three design documents on the "not stored" side.
The newest document sides with storage — but it is a v0.1 draft that describes itself as
summarising the others, so it may be restating the same misreading rather than deciding it.
**Still unresolved, and now more urgent:** an acceptance criterion that contradicts a design
decision will be built to, because it is the one with a test attached.

**Question for the client:** which is authoritative — the design decision or the reference
implementation? Note that the two designs are not equivalent: under "rates not stored," a
*correction* to a historical rate row would flow through to a reprocessed prior-year claim;
under "rates stored," it would not. That is a compliance-relevant difference, not a
refactoring preference.

Note also that the Sprint 6 deliverable — an approval screen showing *"Rates locked at
approval: Free $X.XX, Reduced $X.XX, Paid $X.XX"* — is satisfiable under either design, so the
demo does not disambiguate it.
<!-- source: CSN-Prototype-140826-133159.md#page-14 -->

### B2. Which identity provider? Four different answers {#auth-provider}


⚠️ **Conflict** (blocker) — unresolved. Do not pick a default.
| Source | Says |
|---|---|
| Feature list RF-01, RF-02, RF-04 | **Keycloak** — "Real OIDC login against the demo-state Keycloak realm"; "subdomain → YARP → Keycloak realm → ICnpContext" |
| Sprint plan, Sprints 1, 2 and 5 | **Keycloak** — deployed to staging ECS, realm configured with test users, OIDC login redirects to it |
| Feature list RF-05 | **"Harmony Auth/Cognito decided by client"** |
| Prototype tech stack | **"Harmony & Amazon Cognito — Decision required Sprint 1. Keycloak preferred for demo flexibility; Cognito preferred for ops simplicity."** |
| Infrastructure §3.1 service list | **Cognito** — "OIDC provider (decision required Sprint 1)" |
| Infrastructure §3.4 | **LINQ Harmony Auth preferred**, as reuse over rebuild, with Cognito as the documented fallback |
| Customer deck | **Harmony Auth**, described as "LINQ's centralized authentication service built on Okta and AWS Cognito" |
| Frontend architecture | **Keycloak** — "redirects to ut-doe Keycloak realm → state IdP" |
<!-- source: 51 Feature List.md#RF-01 -->
<!-- source: 51 Feature List.md#RF-05 -->
<!-- source: LINQ CNP - Prototype  Jenny Track - Sprint Plan.md#sprint-1 -->
<!-- source: CSN-Prototype-140826-133159.md#page-4 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-8 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-10 -->
<!-- source: NextGenOverviewEngineering.md#slide-7 -->
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-2 -->

RF-05 is a **Week 0 blocker** — *"Close the Keycloak-vs-Cognito decision in Week 0 before build
starts"* — and Sprint 1 nonetheless lists Keycloak deployment as a deliverable.
<!-- source: 51 Feature List.md#RF-05 -->

Infrastructure §3.4 states the two conditions under which Harmony Auth is chosen, and both must
be **confirmed before the Sprint 1 commit**:

1. Harmony Auth supports per-state tenant isolation at the client/connection level, because
   CNP has one schema per state and the auth layer must mirror that boundary.
2. Client provisioning and teardown can be scripted via API to support on-demand environments.

*"If either cannot be met, fall back to Cognito."*
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-10 -->

**Question:** has this been decided? If not, it blocks ECS provisioning and Secrets Manager
paths, not just login. The Prototype infrastructure checklist meanwhile lists *both* "Cognito
for user auth and M2M" *and* "Harmony JWT Middleware configured for JWKS stateless validation"
in the same line, which suggests the answer may be Harmony-fronting-Cognito.
<!-- source: CSN-Prototype-140826-133159.md#page-7 -->

**New evidence (30 June 2026) — the strongest single statement, and it says Keycloak.** The
Foundational Architecture names it as foundation component **F7**, with the federation model
spelled out: *"One Keycloak deployment on ECS Fargate brokers all state IdPs. Per-tenant realms
federate ClassLink / Okta / Azure AD (Phase 1 OIDC-native states) and SAML/ADFS (Phase 2 SAML
states)."* Keycloak is installed in Mobilization, appears in the frontend shell component, and
is named at three separate points in the Phase-1 vertical walkthrough — including *"State
caseworker logs in (same Keycloak realm, different role)."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-4 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-8 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-11 -->

**Harmony Auth is not mentioned anywhere in that document**, and neither is Cognito.

This moves the weight decisively toward Keycloak, and it is the only source that explains *how*
per-state IdP federation works — which is exactly the capability Infrastructure §3.4 said had
to be confirmed of Harmony Auth before committing to it. **It does not close the question**,
because it does not say Harmony was evaluated and rejected; it simply does not mention it. Ask
whether the §3.4 evaluation happened and what it concluded.

### B3. Are Site Applications in Phase 1 scope? {#site-applications}


⚠️ **Conflict** (blocker) — unresolved. Do not pick a default.
**Four of the six delivered screens are built around a site-application sub-lifecycle that no
Phase 1 requirement describes.**

The screens show: 24 site applications under one sponsor application, each with its own status
(Ready / Attention / Under Review / Returned / Approved / Denied), its own Site Type (Base /
Non-Base), Import Sites and Add Site Application actions, bulk selection, per-site assignment
and a dedicated two-screen management flow.
<!-- source: Ui-Design/cnp_linq_screen_5_site_applications_summary/screen.md#screen -->
<!-- source: Ui-Design/cnp_linq_screen_6_site_application_list/screen.md#screen -->

FRD-03 describes only the sponsor's own annual application, and RF-11 and RF-17 cover only
"the SNP annual application" and a server-defined form. Neither mentions sites.
<!-- source: 03_FRD_Application_Submission.md#section-3 -->
<!-- source: 51 Feature List.md#RF-11 -->

`SiteApp` **is** a first-class workflow entity type with its own condition evaluator and action
executor, so the engine supports it.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-4 -->

**Question:** are the six screens the Phase 1 build scope, or a broader product vision from
which Phase 1 takes a subset? If they are the build scope, the Sprint 4 API contract is
missing every site-application endpoint, and the effort estimate does not include them.

### B4. Are supporting documents in Phase 1 scope? {#documents}


⚠️ **Conflict** (blocker) — unresolved. Do not pick a default.
FRD-03 lists as out of scope: *"document/attachment upload as part of the application (unless
explicitly configured in scope for the demo)."*
<!-- source: 03_FRD_Application_Submission.md#section-6 -->

But the required-documents gate before submission is described as **federally locked and
un-turn-off-able**, the screens show a Supporting Documents card reading "6 of 7 · 1 Missing"
with a Manage Documents action and a Documents item in the primary navigation, and document
gates are a named configuration pattern in the workflow engine.
<!-- source: Application-to-Approval-Journey.md#stage-2 -->
<!-- source: Ui-Design/cnp_linq_screen_3_sponsor_application_packet_overview/screen.md#screen -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-14 -->

**Question:** the parenthetical "unless explicitly configured in scope for the demo" reads like
it was left open deliberately. Has it been closed? A federally-locked document requirement
cannot be demonstrated without document upload.

### B5. Does the Phase 1 lifecycle include a "Returned" state? {#returned-state}


⚠️ **Conflict** (blocker) — unresolved. Do not pick a default.
| Source | Lifecycle |
|---|---|
| FRD-04 FR-4.3 / FR-4.4 | Explicitly requires return-with-explanation and correct-and-resubmit |
| RF-13, RF-15 | "return it with corrections required"; "Draft → Submitted → Under Review → **(Returned)** → Approved, Denied terminal" |
| Prototype demo-state seed | "Draft → Submitted → UnderReview → Approved → **Declined**" — **no Returned state** |
| Sprint 4 gate | "Submit → UnderReview → Approved lifecycle passes" — no Returned |
| The UI | Returned is a first-class status with its own dashboard card, notification and status colour |
| Legacy Iowa CTS | Has `RETURNED` and `WITHDRAWN` |
<!-- source: 04_FRD_Review_Workflow.md#section-3 -->
<!-- source: 51 Feature List.md#RF-15 -->
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->
<!-- source: CSN-Prototype-140826-133159.md#page-12 -->
<!-- source: Ui-Design/cnp_linq_screen_2_sponsor_dashboard/screen.md#screen -->
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#stage-5 -->

Independently, the journey document searched for this and could not confirm it: *"I looked
specifically for this ('Return for corrections,' 'Withdraw,' 'Resubmit') in the platform's
design documentation, and I could not confirm a documented version of this for applications
specifically… This is worth a direct question to your team, not an assumption on my part."*
<!-- source: Application-to-Approval-Journey.md#honest-gap -->

**Question:** the requirements and the UI both require Returned; the prototype seed omits it.
Which is the Sprint 3 seed data? Related: does the Phase 1 lifecycle include **Withdrawn** and
**Closed**, which the UI shows as dashboard cards but no requirement mentions?

**New evidence (30 June 2026) — resolves half of it and introduces a fifth vocabulary.** The
Foundational Architecture states the Phase 1 state machine as:

> **Draft → Submitted → StateReview → ReturnedForCorrection → Approved**
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-6 -->

and the vertical walkthrough confirms the behaviour: *"Caseworker either returns for correction
(a `ReturnedForCorrection` transition with comments…) or approves."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-8 -->

So **a return path IS in Phase 1** — that much is now settled across the requirements, the UI
and the architecture, against the prototype seed alone.

But the same line introduces two new problems:

- **`StateReview`**, not `UnderReview` — a fifth spelling of that state across the corpus.
- **There is no terminal deny state at all.** Neither `Denied` nor `Declined` appears in the
  Phase 1 state machine, and the walkthrough offers the caseworker only "return for correction
  or approve." Yet FRD-04 requires a final determination of Approved *or* Denied, RF-15 marks
  Denied terminal, and the UI has a Denied status card and colour.
<!-- source: 04_FRD_Review_Workflow.md#section-3 -->
<!-- source: 51 Feature List.md#RF-15 -->

A prototype that cannot deny an application is a materially different demo from one that can.

### B6. `Declined` or `Denied`? {#state-naming}


⚠️ **Conflict** (blocker) — unresolved. Do not pick a default.
`StateCode` is a literal string in `WorkflowStates` that the UI, the API contract and the seed
data all key off. The corpus uses both:

- **Declined** — the prototype demo-state seed and the journey document
- **Denied** — FRD-04, RF-15, the design system status list, and every UI screen
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->
<!-- source: Application-to-Approval-Journey.md#stage-5 -->
<!-- source: 04_FRD_Review_Workflow.md#section-3 -->
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#semantic-status-lifecycle -->

Trivial to fix now; expensive after the API contract freezes at the end of Sprint 4.

### B7. What is the demo state? {#demo-state}


⚠️ **Conflict** (blocker) — unresolved. Do not pick a default.
Never stated in any design document — the Prototype plan says *"Demo state-specific hook: TBD
based on demo state selection"* and *"must be identified before Sprint 3."*
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->

**The evidence points strongly to Iowa:** every delivered screen shows Iowa/IA, screen 4 shows
a Des Moines address, the state dropdown defaults to Iowa, a dedicated Iowa CTS legacy analysis
was supplied, and Iowa is the worked configuration example in the journey document (two-stage
approval, addresses sourced from Iowa's EIS).
<!-- source: Ui-Design/cnp_linq_screen_4_sponsor_application/screen.md#screen -->
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#feature-overview -->
<!-- source: Application-to-Approval-Journey.md#config-example -->

But other documents use Utah, Minnesota, Maine, Hawaii, Wisconsin and Alaska as their worked
examples, and the customer deck is written for **Virginia** (VDSS, VDOE, VITA, EO 30, VASNP,
"a Virginia user literally cannot make a request that touches Alabama data").
<!-- source: NextGenOverviewEngineering.md#slide-12 -->
<!-- source: NextGenOverviewEngineering.md#slide-14 -->
<!-- source: NextGenOverviewEngineering.md#slide-7 -->

**Question:** confirm Iowa. Two Sprint-3 dependencies hang on it — the demo-state hook and the
demo-state form configuration — and if it is Iowa, the two-stage approval and the read-only
EIS-sourced address fields are both already specified.

### B8. Which design system? {#design-system}


⚠️ **Conflict** (blocker) — unresolved. Do not pick a default.
RF-46 and the Prototype tech stack mandate **`@linq/snackpaq`**, reusing LINQ's shared
component library and seeding from the Shared Services Starter Angular project.
<!-- source: 51 Feature List.md#RF-46 -->
<!-- source: CSN-Prototype-140826-133159.md#page-3 -->

The delivered `DESIGN.md` specifies a complete and different system — "Public Trust Modern" —
with its own colour tokens, **Public Sans / Source Sans 3** typography, spacing scale, shape
geometry, elevation levels and component specifications. It does not reference snackpaq.
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#brand-style -->

Meanwhile the frontend architecture describes per-tenant branding applied as CSS custom
properties that *"@linq/snackpaq components automatically pick up."*
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-9 -->

**Question:** is Public Trust Modern a theme *for* snackpaq (its tokens map cleanly to CSS
custom properties, which would make this workable), or a replacement? If the latter, RF-46's
64-hour estimate — premised on reuse — is wrong.

---

## HIGH — a wrong guess produces a defect or a compliance gap

### H1. Is `Claims.LateClaimCutoffDays` federally locked? {#late-claim-cutoff}


⚠️ **Conflict** (high) — unresolved. Do not pick a default.
The validation-bounds table marks it **`IsFederal = Yes`**, Min 1, Max 60.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-6 -->

But the same document's Layer 3 example is *"ME.LateClaimCutoffDays = 45 (Maine negotiated a
different window)"*, its effective-dating example future-dates Minnesota to 45, the workflow
engine's flagship worked override is Maine's 60-day late-claim cutoff, and the rules engine
lists *"state-specific late claim policy — Utah allows late originals; other states don't"*
as legitimately configurable.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-1 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-5 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-10 -->
<!-- source: CSN-Rules Engine-140826-132727.md#page-2 -->

If `IsFederal = true`, **every one of those examples would be rejected at write time by the
database trigger.** Separately, the admin UI section says the field shows a range indicator of
**1–90** while the bounds table says Max **60**.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-9 -->

Note the related federal rule is the **60-day claim submission deadline**, which is genuinely
federal and which states cannot extend. A state shortening its own internal cutoff below 60 is
a different thing from extending the federal deadline. The bounds may be conflating them.
<!-- source: CSN-Rules Engine-140826-132727.md#page-2 -->

### H2. `ProgramMealRates` or `ClaimRateAmounts`? {#rate-table-name}


⚠️ **Conflict** (high) — unresolved. Do not pick a default.
Both names are used for what appears to be the same table, sometimes in the same document and
occasionally in the same sentence.

- `ClaimRateAmounts` — the design decisions, the annual-update INSERT statements, the
  configuration domain description
- `ProgramMealRates` — the `FreezeClaimLaws` hook description, the worked
  claim-processing example, and the `cnp_global` contents list, which names **both**:
  *"~387 tables: ProgramMealRates, ClaimRateAmounts (effective-dated), all *Types/*Codes…"*
<!-- source: CSN-Data-140826-132933.md#page-4 -->
<!-- source: CSN-Data-140826-132933.md#page-11 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-13 -->
<!-- source: CSN-Platform Domains-140826-133136.md#page-7 -->

**Question:** one table with an inconsistent name, or two tables with different roles? The
`cnp_global` contents list is the only place both appear together, and it lists them as
separate items.

### H3. Which permission-catalog count is right? {#permission-count}


⚠️ **Conflict** (high) — unresolved. Do not pick a default.
Three incompatible figures:

- **~180 entries** — stated in the ADR, the rights model, and the data document
- **8 domains × ~4 sub-areas × ~5 actions** = 160, given as the derivation of "~180"
- **12 domains and 67 sub-areas** — given in the same rights document as the migration mapping
- **SECURITY 68 entries + CONFIGURATION 347 entries** = 415 for two domains alone, in the ADR
<!-- source: CSN-CNP Rights-140826-132801.md#page-8 -->
<!-- source: CSN-CNP Rights-140826-132801.md#page-12 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-8 -->
<!-- source: CSN-Data-140826-132933.md#page-31 -->

415 for two of eight domains cannot coexist with ~180 total. This matters for Phase 1 because
**SECURITY is the only domain being migrated**, so its true size is the actual Sprint 3 scope.

### H4. Is the rights model role-based or object-level? {#rights-model-conflict}


⚠️ **Conflict** (high) — unresolved. Do not pick a default.
ADR-006 replaces the `CnpObjects` ACL with a role catalog, explicitly rejecting the per-object
model as unmaintainable.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-7 -->

But the customer deck describes the Rights Model as *"Every page and function is a securable
object with individually assignable view, add, modify, delete, and admin rights"* — which is a
description of the ACL model that was rejected.
<!-- source: NextGenOverviewEngineering.md#slide-8 -->

And the Platform Domains document lists **"CnpObjects rights model"** as the content of the
Identity & Access domain.
<!-- source: CSN-Platform Domains-140826-133136.md#page-3 -->

This may be a legacy-inventory line rather than a design statement, but a customer deck
promising per-object rights and an ADR delivering nine roles is a **commitment gap**, not just
a documentation one.

### H5. How many ConfigDefinitions keys does the demo seed? {#config-key-count}


⚠️ **Conflict** (high) — unresolved. Do not pick a default.
- Synthetic data spec: *"All **~180** ConfigDefinitions keys seeded at platform level"*
- Sprint 2 deliverable: *"ConfigDefinitions seeded: **~20** key entries covering application
  workflow (full ~3,000 key seed in later sprint)"*
- Everywhere else: **~3,000** config values
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->
<!-- source: CSN-Prototype-140826-133159.md#page-10 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-1 -->

"~180" is very likely a copy of the *PermissionCatalog* count into the config section. Sprint 2's
"~20, full seed later" reads like the deliberate Phase 1 number.

### H6. Is the audit trail tamper-evident, or just append-only? {#worm}


⚠️ **Conflict** (high) — unresolved. Do not pick a default.
The customer deck promises **S3 Object Lock (WORM) for long-term retention** and calls the trail
*"tamper-evident by design."*
<!-- source: NextGenOverviewEngineering.md#slide-11 -->

No engineering document specifies Object Lock, WORM, hash chaining, or any tamper-*evidence*
mechanism. The engineering position is immutability by absence of an UPDATE/DELETE path plus
database role separation — which prevents casual modification but does not *prove* absence of
modification to an auditor.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-3 -->
<!-- source: CSN-Data-140826-132933.md#page-45 -->

The gap is real: a `cnp_migration` credential or a database restore can alter append-only rows,
and nothing in the design would detect it.

### H7. Does the deck's "three enforcement layers" claim match the design? {#three-layers}


⚠️ **Conflict** (high) — unresolved. Do not pick a default.
The deck says a database trigger *"rejects any direct write that attempts to set IsFederal =
true without meeting the structural preconditions."*
<!-- source: NextGenOverviewEngineering.md#slide-3 -->

The triggers as designed do something different: they reject **tenant override writes that
target a row already marked `IsFederal = true`**. Setting the flag itself is not trigger-guarded
— it is guarded by being migration-only and never exposed in any UI.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-6 -->

The protection is real; the deck's description of the mechanism is not accurate, and an engineer
building to the deck would write the wrong trigger.

### H8. Which claim is right about who can override a `PossibleMatch`? {#ndl-override-scope}


⚠️ **Conflict** (high) — unresolved. Do not pick a default.
FRD-05 business rules say the screening check *"cannot be bypassed by any workflow shortcut,
batch action, or administrative override — **including for state-level admins**."*
<!-- source: 05_FRD_NDL_Screening.md#section-4 -->

FR-5.4 and the flow-gaps design both describe a PossibleMatch being routed to a designated
reviewer who makes an explicit decision, with an `Approved` disposition on `NdlOverrideRequests`
allowing the approval to proceed.
<!-- source: 05_FRD_NDL_Screening.md#section-3 -->
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-2 -->

These are reconcilable — "cannot be bypassed" plausibly means the check always runs and a
ConfirmedMatch is absolute, while a PossibleMatch has a recorded human disposition — but the
words as written conflict, and this is the kind of thing an FNS auditor reads literally.
**Which roles may clear a PossibleMatch?** The corpus never names them.

---

## MEDIUM — inconsistencies that will cost time or credibility

### M1. Rate-table year alignment is off by one {#rate-year-offset}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
The worked example describes an application approved **1 December 2024** producing ClaimLaws
#8821 with `LunFrRte: 4.12`, labelled "SY2025."
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-5 -->

But the rate table gives $4.12 as the **SY2025-26** free lunch rate (effective 1 July 2025) and
$4.05 as SY2024-25. An application approved in December 2024 falls in SY2024-25 and should
freeze $4.05.
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-9 -->

The same example elsewhere calls it *"the record created when their SY2025-26 application was
approved in October 2024"* — also outside the July–June boundary the same document defines.
<!-- source: CSN-Data-140826-132933.md#page-6 -->

The labelling is also inconsistent: "SY2025" and "SY2025-26" are used interchangeably.

### M2. Two full rate tables that do not agree {#rate-tables}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
| Rate | The Math (labelled SY2026-27) | Annual Rate Updates (SY2025-26) |
|---|---|---|
| NSLP Lunch Free | $4.28 | $4.12 |
| NSLP Lunch Reduced | $3.97 | $3.82 |
| NSLP Lunch Paid | $0.53 | $0.50 |
| SBP Breakfast Free | $2.39 | $2.27 |
<!-- source: CSN-The Math-140826-133113.md#page-1 -->
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-9 -->

These are consistent as *different years* (the deltas match the +3.9% / +6% described in the
CSN-Data example), so this is probably fine — but The Math presents its table as "The Full Rate
Table (SY2026-27)" with no effective date column, and **synthetic data seeding will use whichever
table the engineer opens first.** RF-51/Sprint 8 requires the demo to show real published rates.
<!-- source: CSN-Data-140826-132933.md#page-5 -->
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->

### M3. When does the program year rollover job fire? {#rollover-date}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
Three answers **in one document**, and a fourth elsewhere:

- Prose: *"Every July 1, the platform needs to roll every active sponsor's agreements forward"*
- Diagram: *"AutoGenerated · Hangfire · **Oct 1**, midnight"*
- Code comment: *"Fires: `0 0 1 7 *` (**midnight UTC, October 1**)"* — the cron expression is
  July 1; the comment says October 1
- Rate-availability note: *"The rollover job (firing **~May 1**)…"*
- CSN-Data: *"the annual job that rolls every application forward into a new program year at
  **midnight on October 1**"*
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-3 -->
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-5 -->
<!-- source: CSN-Data-140826-132933.md#page-38 -->

All four dates are defensible for *some* program (NSLP July, CACFP October, SFSP spring), which
is probably the origin of the confusion — but the job as written takes a single schedule.

Related: `ProgramGroupYears` states NSLP/SBP run July–June, and two sentences earlier the same
document says *"When USDA publishes a new school year starting October 1, this is where that
year is registered."*
<!-- source: CSN-Data-140826-132933.md#page-8 -->

### M4. How many domains? Four different counts {#domain-count}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
| Count | Source |
|---|---|
| **25** domains across 4 authority tiers | CSN-Data, and the Prototype's design-document index |
| **28** domains | FRD Index and FRD-08 |
| **31** domains, 4 tiers | Customer deck speaker notes |
| **33** by enumeration | Platform Domains, counting the tier lists |
<!-- source: CSN-Data-140826-132933.md#page-1 -->
<!-- source: CSN-Prototype-140826-133159.md#page-19 -->
<!-- source: 00_FRD_Index.md#section-1 -->
<!-- source: NextGenOverviewEngineering.md#slide-4 -->
<!-- source: CSN-Platform Domains-140826-133136.md#page-1 -->

### M5. Is 1,402 tables the legacy footprint or the greenfield target? {#table-count}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
FRD-08 attributes it to the **current system**: *"replacing a large legacy footprint (1,402
tables across 28 domains in the current system)."*
<!-- source: 08_FRD_Delivery_Foundation.md#section-1 -->

CSN-Data attributes 387 + 1,015 = 1,402 to the **new design**, and gives the legacy CTS count
as **1,243** tables.
<!-- source: CSN-Data-140826-132933.md#page-3 -->
<!-- source: CSN-Data-140826-132933.md#page-48 -->

The collapse arithmetic does not close either: 840 absorbed + 413 "Keep" + 180 eliminated =
1,433 against a stated 1,243.
<!-- source: CSN-Data-140826-132933.md#page-48 -->

Phase 1's actual target is much smaller and stated clearly: **~20–30 `cnp_global` and ~60–80
`cnp_ops` tables, with other domains shipped as empty migration stubs.**
<!-- source: 51 Feature List.md#RF-42 -->

### M6. Is it database-per-tenant or schema-per-tenant? {#tenancy-terminology}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
The ADR is titled *"Database-per-tenant: separate Aurora **schema** per state, no TenantId
column"* — self-contradictory in its own title — and its body describes schemas within one
`cnp_ops` cluster.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-6 -->

Infrastructure §1.1 is unambiguous: **one cluster, one schema per state**, and §7.4 draws the
correct consequence that a single cluster failure affects all states at once.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-1 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-16 -->

But CSN-Data and Platform Domains both say *"1,015 tables live in a separate cnp_ops
**database** per state"* and *"cnp_ops (**1 Aurora per state**)"*, and RF-41 says *"Two Aurora
PostgreSQL databases."*
<!-- source: CSN-Data-140826-132933.md#page-3 -->
<!-- source: CSN-Platform Domains-140826-133136.md#page-1 -->
<!-- source: 51 Feature List.md#RF-41 -->

The **design intent is settled** (schemas in one cluster) but the language is not, and the two
**New evidence (30 June 2026) — and it makes this worse, not better.** The Foundational
Architecture states cluster-per-state as a design principle, not a slip: *"A separate Aurora
cluster per state means there is no TenantId column on operational tables"*, F2 is described as
*"One Aurora Postgres instance per state"*, and onboarding a new state is listed as requiring
*"a cnp_ops Aurora cluster."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-3 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-10 -->

Infrastructure §1.2 **explicitly evaluated and rejected** separate clusters per state as
*"cost-prohibitive at 28 states"*, requiring 28 independent migration pipeline runs with
unacceptable connection-pool overhead.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-2 -->

So this is **no longer a vocabulary inconsistency — it is two documents specifying opposite
architectures**, one of which the other rejected by name. It changes the cost model, the DR
runbook (a single cluster failure affecting all states versus one), the migration runner, and
the connection-pooling design. Note also that F3 places `cnp_ext` *"in the same Aurora cluster
as cnp_ops"*, which only parses under the single-cluster model.
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-3 -->

Both readings still

have materially different cost, DR and connection-pooling consequences. Worth normalising the
vocabulary before it reaches an infrastructure estimate.

### M7. Where do tenant config overrides live? {#config-override-location}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
Configuration Defaults and the ADR both place `TenantConfigOverrides` in **`cnp_ops`**.
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-3 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-5 -->

Platform Domains says state-specific values are *"stored as effective-dated rows in
**cnp_global** config schema."*
<!-- source: CSN-Platform Domains-140826-133136.md#page-8 -->

The DC-feed example in CSN-Data also reads tenant config *"from cnp_global [config] schema."*
<!-- source: CSN-Data-140826-132933.md#page-17 -->

This matters for the config-resolution index and for whether a state's overrides survive a
per-state schema restore.

### M8. Which environment model? {#environment-model}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
Infrastructure §3.2: *"All Ephemeral Except Production"* — dev on-demand per engineer, test per
PR, staging per release candidate, UAT and demo per event.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-8 -->

RF-49: *"dev + staging on shared Aurora; demo + UAT on dedicated clusters."* Sprint 1 and the
Prototype environment table describe persistent dev and staging with nightly data resets.
<!-- source: 51 Feature List.md#RF-49 -->
<!-- source: CSN-Prototype-140826-133159.md#page-6 -->

Fully-scripted on-demand provisioning is a substantially larger DevOps scope than persistent
shared environments, and RF-49 is estimated at 40 hours.

### M9. Secrets path convention has three shapes {#secret-path-shape}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
Canonical: `cnp/{environment}/{tenant-or-global}/{category}/{name}`.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-5 -->
<!-- source: CSN-Secrets Management-140826-132810.md#page-2 -->

But the DC feed examples in the same Infrastructure document use `cnp/dc/IN/sftp` and
`cnp/dc/IN/pgp` — no environment segment and the category before the tenant.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-18 -->

And Access Governance gives `cnp/prod/{tenant-or-global}/{category}/{name}` with `prod`
hardcoded rather than an `{environment}` variable. A worked example elsewhere also shows
`cnp/prod/ut/db-connection` — four segments, not five.
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-4 -->
<!-- source: CSN-Secrets Management-140826-132810.md#page-1 -->

Path shape is load-bearing: IAM policies are written as path prefixes, and per-tenant isolation
depends on the tenant segment being in a predictable position.

### M10. Sprint numbering is offset by one {#sprint-numbering}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
The feature list labels sprints Mob / S1–S5 / H across 14 weeks; the sprint plan and prototype
use Sprint 1–8 across 16 weeks. They map by *week*, not by number: feature-list "S1, Weeks 3-4"
is sprint-plan "Sprint 2, Weeks 3–4."
<!-- source: 51 Feature List.md#feature-detail -->
<!-- source: LINQ CNP - Prototype  Jenny Track - Sprint Plan.md#sprint-1 -->

Anyone tracking "which sprint is RF-18 in?" will get two different answers. **Always cite weeks.**

### M11. Sprint 2's dates are wrong {#sprint-2-dates}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
*"Sprint 2 · Weeks 3–4 · August 31–September 1"* — a two-day sprint. Appears identically in both
the prototype plan and the sprint plan, so it is an error in the source, not the extraction.
Probably September 11.
<!-- source: CSN-Prototype-140826-133159.md#page-10 -->
<!-- source: LINQ CNP - Prototype  Jenny Track - Sprint Plan.md#sprint-2 -->

Also: the environment table says demo-state UAT runs **Weeks 13–15** while Sprint 7 is **Weeks
13–14**.
<!-- source: CSN-Prototype-140826-133159.md#page-6 -->

### M12. .NET 8 or .NET 10? {#dotnet-version}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
Every architecture and feature document says **.NET 8**. The Prototype infrastructure checklist
says *"ECS Fargate cluster with task definition for the CNP API (ASP.NET Core, ... **Core 10**)."*
<!-- source: CSN-Prototype-140826-133159.md#page-3 -->
<!-- source: CSN-Prototype-140826-133159.md#page-7 -->
<!-- source: 51 Feature List.md#RF-45 -->

### M13. Is FNS-44 renamed? {#report-naming}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
Annual Rate Updates is explicit that report numbers are **unchanged** by the FNS→FNA rename.
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-1 -->

Frontend Architecture writes *"**NA-44** federal reports"* in prose and
`reportType: "**FNA-44**"` in its code sample.
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-5 -->

A renamed report type code would break the report registry.

### M14. Is SMP (Special Milk Program) in the program list? {#smp}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
`FederalProgramDefinitions` is described as the canonical list: *"NSLP, SBP, SFSP, CACFP, SSFO,
FFVP."* No SMP.
<!-- source: CSN-Data-140826-132933.md#page-47 -->

But Platform Domains lists SMP under SNP, the customer deck lists *"NSLP · SBP · CACFP · SFSP ·
SMP · CEP"*, and the Formly field config has an `avgCostHalfPint` field *"Required only if
Special Milk Program is active"* keyed on `programCodes.includes("SMP")`. The rate-change list
also names *"special milk rates."*
<!-- source: CSN-Platform Domains-140826-133136.md#page-3 -->
<!-- source: NextGenOverviewEngineering.md#slide-10 -->
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-6 -->
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-1 -->

### M15. Site "Eligibility" is modelled as Free/Reduced/Paid {#site-eligibility}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
Screen 6 shows an **Eligibility** column and filter on the site-application list with values
Free, Reduced and Paid — Lincoln Elementary "Free", Washington Middle "Reduced", Jefferson High
"Paid".
<!-- source: Ui-Design/cnp_linq_screen_6_site_application_list/screen.md#screen -->

Free/Reduced/Paid is a **per-child eligibility category**, not a site attribute. A site's
relevant classifications are Base/Non-Base (Provision 2/3), CEP participation and ISP, and
severe-need qualification.
<!-- source: CSN-The Math-140826-133113.md#page-1 -->
<!-- source: CSN-The Math-140826-133113.md#page-5 -->

Likely a mockup shortcut, but if it reaches the schema it produces a column that cannot be
populated correctly.

### M16. When does rate management exist? {#rate-management-phase}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
The Configuration-vs-Deployment table lists updating annual rates under **"Rate Management API
(Phase 2)."**
<!-- source: CSN-Code Deployment vs Configuration-140826-133128.md#page-5 -->

Annual Rate Updates and CSN-Data present the June 2026 rate update as the **first
proof-of-concept of the new architecture**, already exercised.
<!-- source: CSN-Data-140826-132933.md#page-4 -->
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-9 -->

Probably reconcilable — a raw INSERT works now, the *API* is Phase 2 — but the zero-deployment
rate story is a headline claim and should be stated consistently.

### M17. The `LateClaimCutoffDays = 6` typo {#cutoff-typo}


⚠️ **Conflict** (medium) — unresolved. Do not pick a default.
Both the rights document and the configuration document give the platform default as
*"`LateClaimCutoffDays = 6`"*, while the bounds table and the Minnesota example both use 60.
<!-- source: CSN-CNP Rights-140826-132801.md#page-1 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-1 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-6 -->

Trivial, but it would be seeded verbatim into `ConfigDefinitions` by someone reading only that
page.

---

## NEW — raised by the Foundational Architecture (30 June 2026)

Conflicts that did not exist in the corpus until the most recent document arrived. It is the
only document with an explicit layering model and the only one with **foundation acceptance
criteria**, so its additions carry weight — but it is a v0.1 draft.

### N1. Phase 1 must provision a second state — or must not {#second-state}

⚠️ **Conflict** (blocker) — unresolved. Do not pick a default.

**Three of the ten foundation acceptance criteria require a second synthetic state inside Phase
1**, and the tenth makes it the Definition of Done:

- Criterion 1 — tenant isolation *"verified by introducing a second synthetic state into
  cnp_ops, provisioning a TenantRegistry row, and demonstrating that a user logged into one
  state cannot see the other state's data even via direct API call"*
- Criterion 8 — *"a second synthetic state can be provisioned end-to-end (cnp_ops cluster +
  schema + seed data + TenantRegistry row + Keycloak realm) by running the migration runner
  only, with no application code change"*
- Criterion 9 — *"a second synthetic state's subdomain renders with the second state's brand
  tokens, OIDC realm, and feature-flag set, without a frontend code change"*
- Criterion 10 — *"the LINQ configuration team can re-execute the prototype outcome on a
  different demo state without a single new line of code"*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-11 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-12 -->

The Prototype document states the direct opposite as a **hard constraint**: *"One state only.
The prototype environment is configured for one demo state. **No multi-state scenarios, no
cross-state features.**"*
<!-- source: CSN-Prototype-140826-133159.md#page-1 -->

FRD-01 splits the difference — *"Phase 1 wires exactly one state's identity realm; the
architecture must not require code changes to add a second state later"* — which is a design
constraint, not a demonstration.
<!-- source: 01_FRD_Identity_Access.md#section-5 -->

**This is real scope, not wording.** A second Keycloak realm, a second schema (or cluster), a
second brand token set, a second synthetic dataset, and a migration runner proven end to end
appear in no sprint, no feature, and no hour of the 2,264-hour estimate. Criterion 10 is
substantially harder than anything in the prototype's demo-readiness list.

### N2. Characterization tests against a legacy stored procedure the team cannot see {#characterization-access}

⚠️ **Conflict** (high) — unresolved. Do not pick a default.

Phase 1 test scope includes *"characterization tests against the legacy SNP
application-approval stored procedure (≥ 80% branch coverage)."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-8 -->

Three constraints make that impossible as written:

- *"Offshore engineers have no access to any existing LINQ system — not CTS, not DIS, not any
  current LINQ database, codebase, or infrastructure."*
<!-- source: CSN-Prototype-140826-133159.md#page-1 -->
- Several legacy stored procedures are **deliberately encrypted**, and *"the offshore team
  cannot characterize or reimplement what those procedures do without seeing them first."*
<!-- source: CSN-Data-140826-132933.md#page-3 -->
- Replay validation against real CTS/DIS data is explicitly scoped as *"onshore-only work done
  during state migration — not part of the greenfield prototype."*
<!-- source: CSN-Prototype-140826-133159.md#page-15 -->

**Question:** is this onshore work inside the Phase 1 window, is the SNP approval procedure
among the unencrypted ones, or is the criterion aspirational? An 80% branch-coverage target
against unavailable source is not a plan.

### N3. Phase 1 surface is larger here than in the feature list {#phase-1-surface}

⚠️ **Conflict** (high) — unresolved. Do not pick a default.

Deliverables the Foundational Architecture puts in Phase 1 that have **no RF number and no
hours** in the 51-feature, 2,264-hour list:

| Deliverable | Source |
|---|---|
| **Notification Service** built, with templates wired for application-state-change emails (F14), plus notifications fired on submit, return and federal block | page 5, page 8 |
| **Audit Timeline query API live** (F13) — RF-39 covers the *screen*, not an API | page 5 |
| **Snowflake account provisioned** and CDC pipeline scaffolded (F4), in Mobilization | page 3, page 11 |
| **Tenant Registry** table and seeded row (F6) — appears in no other document | page 4 |
| **Federal Report Engine contracts scaffolded** (E5) | page 6 |
| **Rules Engine scaffolded** with state-configurable application-validation rules (E2) | page 6 |
| **`cnp_ext` scaffolded** (F3) | page 3 |
| **Terraform**, **AWS CodeDeploy**, **per-PR ephemeral environments** | page 9 |
| **Playwright E2E** and **xUnit on every Layer-1 service** | page 8 |
| **Per-state migration runner** in place for Phase-2 multi-state (F2) | page 3 |
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-3 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-5 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-6 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-8 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-9 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-11 -->

Individually small; collectively a different Phase 1. **Question:** is the feature list the
committed scope and this document the architectural intent, or has scope grown since?

### N4. `EntitySnapshots` — prior state or state at transition? {#snapshot-timing}

⚠️ **Conflict** (medium) — unresolved. Do not pick a default.

The Foundational Architecture describes it as *"`EntitySnapshots` (full **prior-state**
JSONB)"*.
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-5 -->

Every other description says it captures the entity **at** the transition — *"a full structured
snapshot of a record's key fields at each status transition"*, answering *"what was the
enrollment count on this application **at the time of approval**?"*
<!-- source: CSN-Data-140826-132933.md#page-43 -->

Before-versus-at is not a nuance in an audit table. It determines whether "what did this
application look like the day it was approved" is answered by the approval row or the one after
it, and the point-in-time reconstruction guarantee depends on knowing which.

### N5. The `IsFederal` surface has six carriers, or five, or four {#isfederal-carriers}

⚠️ **Conflict** (medium) — unresolved. Do not pick a default.

The Foundational Architecture states *"every CnpDefault, RolePermission, WorkflowTransition,
**FormField**, and **ComplianceRuleDef** carries an `IsFederal` column."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-4 -->

ADR-007 lists four levels — config values, workflow states, workflow transition conditions and
actions, and permission catalog entries — with no mention of form fields or compliance rule
definitions.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-9 -->

`FormField.IsFederal` is a genuinely useful idea (a federally mandated form field that a state
cannot hide) and it appears nowhere else, including in the Form Engine description. If it is
real it is a schema column and a write-time check that nobody has scheduled.

### N6. A fourth number for the Phase 1 permission seed {#permission-seed-count}

⚠️ **Conflict** (medium) — unresolved. Do not pick a default.

F8's Phase-1 scope: *"Phase-1 SECURITY domain RolePermissions seeded (**~25 permissions**)."*
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-4 -->

Against **68** for the SECURITY domain in the ADR, **~180** total in three documents, and
**415** implied by SECURITY 68 + CONFIGURATION 347. See also `#permission-count`.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-8 -->

~25 may be the *seeded* subset rather than the domain's full catalog, which would reconcile it —
but nothing says so.

## MISSING — referenced but not supplied

### X1. Documents cited as inputs that are not in this handover {#missing-documents}


⚠️ **Conflict** (missing input) — not supplied by the client.
The FRD index derives itself from four sources, three of which were not supplied:

- `CNP_Phase1_High-Level_Test_Plan.docx` — quality strategy, 13 test suites TS-01–TS-13,
  demo-readiness DoD
- `CNP_Phase1_Test_Execution_Sprint_Plan.xlsx` — **83 scenarios SC-101–SC-1303**, with full
  RF → suite → scenario traceability
- `CNP_ERD.html` — the legacy entity map, referenced by nearly every design document as the
  authority for table names, columns and relationships
<!-- source: 00_FRD_Index.md#section-1 -->

The index also links two further documents in the same set:

- `09_TDD_Plan.md` — the test-first companion mapping every functional requirement to a failing
  test, cross-referenced to the QA scenario IDs
- `10_Test_Strategy.md` — layers and ownership, risk focus, environments, sprint gates, defect
  rules
<!-- source: 00_FRD_Index.md#section-7 -->
<!-- source: 00_FRD_Index.md#section-8 -->

**Every FRD cross-references TS-01–TS-13, and no document in this handover defines them.**
Without the test plan and the execution workbook, RF → TS → SC traceability cannot be
reconstructed, and the QA engineers have no scenario catalog.

The Prototype design-document index additionally names a **Testing Strategy** document
(*"§4 IsFederal guardrail assertions (7 required), §8 per-PR gates. QA engineer reads this
first"*) which was not supplied — so **the seven required guardrail assertions are named as a
gate but never enumerated.**
<!-- source: CSN-Prototype-140826-133159.md#page-20 -->

Also referenced and absent: `CNP_October_Plan.html` (the demo script, needed for the Sprint 7
dry run) and `CNP_Architecture…e1.pptx`.
<!-- source: CSN-Prototype-140826-133159.md#page-15 -->
<!-- source: CSN-Prototype-140826-133159.md#page-2 -->

The Foundational Architecture adds two more:

- **The Synopsis** — which *"names it as five blocks (Platform Foundation, Engines,
  Configuration & Access, Integrations, Operations & Safety)"*. A fifth structural taxonomy of
  the platform, alongside the four tiers, the four layers, and the three configuration layers.
- **The v0.2 proposal**, whose **Section 5.3** defines the onboarding test that is a Hardening
  deliverable and effectively the foundation's Definition of Done.
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-12 -->
<!-- source: CNP_Foundational_Architecture_v0.1 2 (1).md#page-11 -->

### X2. The Data Flow Document has no text layer {#data-flow-diagram}


⚠️ **Conflict** (missing input) — not supplied by the client.
`CSN-Data Flow Document-140826-133146.pdf` contains only a draw.io diagram export. The
extracted text is four lines: a title, "To edit, open this file at draw.io", the diagram name
`CNPDataFlow`, and a date.
<!-- source: CSN-Data Flow Document-140826-133146.md#page-1 -->

The Prototype index describes what it should contain: *"Auth lane browser login → WAF/API GW →
Core API redirect → Harmony Auth login page → JWT (Bearer) issuance → subsequent API requests
validated against that JWT with CNP RBAC applied."*
<!-- source: CSN-Prototype-140826-133159.md#page-20 -->

**Request:** the `.drawio` source, or a PNG/SVG export. Note this description names **Harmony
Auth** and adds a **WAF / API Gateway** in front of the Core API that appears in no other
document.

### X3. Diagrams lost in every PDF {#lost-diagrams}


⚠️ **Conflict** (missing input) — not supplied by the client.
The PDFs were exported from a wiki and their diagrams did not survive as text. Named but
unavailable: the claim lifecycle state machine (with red borders marking federal transitions),
the application lifecycle state machine, the additional state machines, the workflow admin UI
screens, the AWS architecture diagram and the data flow diagram (deck slides 15–16), and the
domain map.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-8 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-10 -->
<!-- source: NextGenOverviewEngineering.md#slide-15 -->
<!-- source: NextGenOverviewEngineering.md#slide-16 -->

The tabular data around them survived, so this is a completeness gap rather than a blocker.

### X4. Values marked TBD in the sources themselves {#tbd}


⚠️ **Conflict** (missing input) — not supplied by the client.
| Item | Status | Needed by |
|---|---|---|
| Demo state selection | TBD | Before Sprint 3 |
| Demo state-specific hook | TBD — *"identified by onshore config specialist"* | Before Sprint 3 (Sprint 4 acceptable) |
| Speed-demo config key | TBD | Before Sprint 6 |
| Migration tooling — FluentMigrator or EF Core | Decision pending | Sprint 2 |
| Infrastructure credential rotation frequency | *"TBD — needs infosec input"* | Before production |
| MO/DHSS split-state design | *"a known pending item"* | Before DIS migration |
| Food Distribution scope (128–304 tables, cannot be cleanly separated) | *"Decision required before Phase 3"* | Before migration planning |
| Ohio / Wyoming / Iowa / Hawaii extension schemas | *"require decisions before Phase 3"* | Before Phase 3 |
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->
<!-- source: CSN-Prototype-140826-133159.md#page-11 -->
<!-- source: CSN-Prototype-140826-133159.md#page-4 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-6 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-12 -->
<!-- source: CSN-Data-140826-132933.md#page-37 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-3 -->

### X5. Hard gates that are not started {#not-started-gates}


⚠️ **Conflict** (missing input) — not supplied by the client.
Three items are described as **hard gates** and recorded as not started or fabricated. Each
blocks something in the Phase 1 or go-live path:

| Gate | Status | Blocks |
|---|---|---|
| Break-glass access management system | **Not started** | Provisioning any production environment |
| NIST SP 800-171 gap assessment (110 requirements) | **Not started** | Provisioning any production environment |
| DR plan — annotated in the source as *"This is completely fabricated. Need to discuss with Ed."* | Under assessment | First state production go-live |
| Synthetic test data pipeline | Not started | Offshore development beginning |
| Offshore DLP controls | Not started | Offshore receiving any environment access |
| Offshore contractor registry | Pending — *"Immediately"* | — |
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-6 -->
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-7 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-12 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-14 -->

The last two gate the offshore team starting at all, and the sprint plan has them starting in
Week 1.

### X6. Encrypted legacy stored procedures {#encrypted-procs}


⚠️ **Conflict** (missing input) — not supplied by the client.
Several legacy stored procedures were deliberately encrypted to protect LINQ IP. The offshore
team *"cannot characterize or reimplement what those procedures do without seeing them first."*
Two things are needed before those modules can be assigned to a sprint: decrypted source, and
time from the engineers who built them.
<!-- source: CSN-Data-140826-132933.md#page-3 -->

Not a Phase 1 blocker — Phase 1 is greenfield — but it blocks the characterization tests that
several documents require before any legacy stored procedure is retired.
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-8 -->

---

## Questions that are simply unanswered {#unanswered}

Not contradictions — the documents just never say.

1. **What is the demo state's specific workflow customization?** The whole prototype narrative
   turns on demonstrating one real state customization, and it is TBD in every document.
2. **Which roles may clear an NDL PossibleMatch?** "A designated reviewer" is as specific as
   the corpus gets.
3. **What status does a reinstated application land in** after a successful appeal — Approved,
   or back to Under Review? Explicitly flagged as undocumented.
<!-- source: Application-to-Approval-Journey.md#appeal -->
4. **Are Withdrawn and Closed part of the Phase 1 lifecycle?** They appear in the UI and the
   design system; no requirement mentions them.
5. **What are the 7 required IsFederal guardrail assertions?** Named as a Sprint 7 gate and a
   demo-readiness criterion; enumerated nowhere in this handover.
6. **What is the Phase 1 form definition for the demo state?** RF-17 requires a server-defined
   form; screen 4 shows section 1 of 7; sections 2–7 have no field inventory anywhere.
7. **Is `PREAPPROVAL_1` (the legacy NSLP-only intermediate approval gate) in scope?** It is what
   Iowa's documented "two-stage approval" actually is in the legacy system.
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#stage-5 -->
<!-- source: Application-to-Approval-Journey.md#config-example -->
8. **Does the sponsor see state-side actor names?** The mockups show "State Reviewer" and "State
   Administrator" in the sponsor's own Updated-By column. That is a disclosure decision, not a
   UI detail.
<!-- source: Ui-Design/cnp_linq_screen_6_site_application_list/screen.md#screen -->

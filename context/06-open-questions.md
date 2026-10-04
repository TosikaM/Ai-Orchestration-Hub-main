<!-- PROJECT CONTEXT — synthesised, not a source document.

     Every factual claim here needs a provenance comment naming where it came from:
         <!-- from: knowledge/distilled/<topic>.md#<anchor> -->
     `python scripts/project-context.py check` fails on a claim without one.

     If a statement has no source, it is an ASSUMPTION. Move it to 06-open-questions.md
     with the assumption stated, rather than leaving it here where the next reader will
     take it for a requirement. -->

# Open questions

The build-affecting subset of the 45 conflicts recorded in
`knowledge/distilled/99-contradictions-and-open-questions.md`, ordered by **what breaks if we
guess wrong** — not by how hard the question is.

> **Updated after `CNP_Foundational_Architecture_v0.1` (30 June 2026) arrived mid-ingestion.**
> It is the newest document in the corpus and the only one carrying **foundation acceptance
> criteria**. It shifts questions 1, 2 and 6 below, hardens the tenancy disagreement, and adds
> six new conflicts — the largest of which is that its acceptance criteria require Phase 1 to
> provision a **second state**, which the Prototype document forbids in the same breath.
<!-- from: knowledge/distilled/13-foundational-architecture.md#acceptance -->

None of these has been resolved. The client's own rule is that a design document beats a build
plan and that conflicts are flagged rather than silently settled, so picking a plausible default
here would be the specific failure they warned against.
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#precedence -->

---

## Ask before Week 0 {#week-0}

| # | Question | Why it cannot wait | Detail |
|---|---|---|---|
| 1 | **Does `ClaimLaws` store dollar rates, or only the eligibility tier?** | It determines the table schema and the claim calculation service signature. Three design documents say rates are *not* stored; the reference C# implementation reads them directly off the object — **and the newest document makes "rates are written into the ClaimLaws row" a foundation acceptance criterion.** An acceptance criterion that contradicts a design decision gets built to, because it is the one with a test attached | `99#claimlaws-rates` |
| 2 | **Which identity provider?** | RF-05 calls this a Week 0 blocker. **The newest document says Keycloak unambiguously**, as foundation component F7, and is the only source that explains how per-state IdP federation works (realms federating ClassLink / Okta / Azure AD, with SAML/ADFS in Phase 2). It does not mention Harmony Auth or Cognito at all — so it moves the weight decisively without formally closing the §3.4 evaluation | `99#auth-provider` |
| 3 | **Is the demo state Iowa?** | Two Sprint-3 dependencies hang on it. Every delivered screen shows Iowa; every design document says "TBD". If it is Iowa, the two-stage approval and read-only EIS-sourced address fields are already specified for us | `99#demo-state` |
| 3b | **Must Phase 1 provision a second state?** | Three of the ten foundation acceptance criteria require it, and the tenth makes *"re-execute the prototype on a different demo state without a single new line of code"* the Definition of Done. The Prototype document states the opposite as a hard constraint: *"One state only. No multi-state scenarios."* This is real, unestimated scope — a second realm, schema, brand token set, dataset, and a migration runner proven end to end | `99#second-state` |
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#claimlaws-rates -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#auth-provider -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#demo-state -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#second-state -->

## Ask before the API contract freezes {#before-contract-freeze}

The contract freezes at the end of Weeks 7–8 and *"must not change"* after. These four all
change it.
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#sprint-4 -->

| # | Question | Why it matters | Detail |
|---|---|---|---|
| 4 | **Are site applications in Phase 1 scope?** | Four of six delivered screens are built around a site-application sub-lifecycle that no requirement describes. If they are in scope, the Sprint 4 contract is missing every site endpoint and the estimate does not include them | `99#site-applications` |
| 5 | **Is supporting-document upload in Phase 1?** | FRD-03 lists it out of scope *"unless explicitly configured in scope for the demo"* — which reads as deliberately left open. But the federally-locked document gate cannot be demonstrated without upload | `99#documents` |
| 6 | **Does the Phase 1 lifecycle include Returned — and can an application be Denied at all?** | The return path is now settled: requirements, UI and the newest architecture all have it. But that architecture states the Phase 1 machine as **Draft → Submitted → StateReview → ReturnedForCorrection → Approved** — with **no terminal deny state**, and a fifth spelling of Under Review. FRD-04 requires a determination of Approved *or* Denied. A prototype that cannot deny an application is a materially different demo | `99#returned-state` |
| 7 | **`Declined` or `Denied`?** | `StateCode` is a literal that the UI, the API contract and the seed data all key off. The corpus uses both. Trivial now; expensive after the freeze | `99#state-naming` |
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#site-applications -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#documents -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#returned-state -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#state-naming -->

## Ask before seeding config or building the rights model {#before-seed}

| # | Question | Why it matters | Detail |
|---|---|---|---|
| 8 | **Is `Claims.LateClaimCutoffDays` federally locked?** | The bounds table marks it `IsFederal = Yes`. If so, **the database trigger would reject Maine's and Minnesota's overrides — the flagship worked examples in two other documents.** The genuinely federal rule is the 60-day *submission deadline*, which is a different thing from a state's internal cutoff; the bounds may be conflating them | `99#late-claim-cutoff` |
| 9 | **`ProgramMealRates` or `ClaimRateAmounts`?** | Both names are used for what looks like one table. The `cnp_global` contents list is the only place both appear together — and lists them as separate items | `99#rate-table-name` |
| 10 | **How large is the SECURITY permission domain?** | Phase 1 migrates SECURITY only, so its true size *is* the Sprint 3 scope. The corpus gives ~180 total entries, and separately 68 for SECURITY + 347 for CONFIGURATION — which cannot both be true | `99#permission-count` |
| 11 | **How many ConfigDefinitions keys does the demo seed — ~20 or ~180?** | "~180" is very likely the PermissionCatalog count copied into the config section; Sprint 2's "~20, full seed later" reads like the real number | `99#config-key-count` |
| 12 | **Where do `TenantConfigOverrides` live — `cnp_ops` or `cnp_global`?** | Affects the config-resolution index, and whether a state's overrides survive a per-state schema restore | `99#config-override-location` |
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#late-claim-cutoff -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#rate-table-name -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#permission-count -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#config-key-count -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#config-override-location -->

## Commitments in the customer deck that engineering has not designed {#commitment-gaps}

These are not documentation inconsistencies — they are things a customer has been shown that the
engineering design does not currently deliver.

| # | Gap | Detail |
|---|---|---|
| 13 | **The deck promises S3 Object Lock (WORM) and a "tamper-evident" audit trail.** No engineering document specifies Object Lock, WORM, or any tamper-*evidence* mechanism. Append-only-by-absence-of-a-DELETE-path prevents casual modification; it does not prove to an auditor that nothing was modified | `99#worm` |
| 14 | **The deck describes per-object rights** — "every page and function is a securable object with individually assignable view, add, modify, delete and admin rights" — which is the ACL model ADR-006 explicitly rejected in favour of nine roles | `99#rights-model-conflict` |
| 15 | **The deck describes the database trigger incorrectly**, as rejecting writes that *set* `IsFederal = true`. The triggers reject tenant overrides that *target* a federal row. The protection is real; an engineer building to the deck would write the wrong trigger | `99#three-layers` |
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#worm -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#rights-model-conflict -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#three-layers -->

## Documents referenced as inputs but not supplied {#missing-inputs}

| # | Missing | Consequence |
|---|---|---|
| 16 | `CNP_Phase1_High-Level_Test_Plan.docx` — defines **TS-01–TS-13** | Every FRD cross-references these suites. Nothing in this handover defines them |
| 17 | `CNP_Phase1_Test_Execution_Sprint_Plan.xlsx` — **83 scenarios SC-101–SC-1303** with full RF → suite → scenario traceability | **QA has no scenario catalog.** Traceability cannot be reconstructed |
| 18 | `CNP_ERD.html` — the legacy entity map | Referenced by nearly every design document as the authority for table names, columns and relationships |
| 19 | `09_TDD_Plan.md` and `10_Test_Strategy.md` | Linked from the FRD index; the test-first companion and the program-level quality approach |
| 20 | The **Testing Strategy** document | It is where **the seven required IsFederal guardrail assertions** are enumerated. They are a demo-readiness gate and are named nowhere else |
| 21 | `CNP_October_Plan.html` — the demo script | Needed for the Sprint 7 dry run, which is timed against it |
| 22 | The **Data Flow Document** source | The supplied PDF is a draw.io export with no text layer. The `.drawio` file or a PNG/SVG would resolve it. Its description also names a **WAF / API Gateway** that appears in no other document |
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#missing-documents -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#data-flow-diagram -->

## Gates that are not started {#not-started}

Not questions — status. Each is described in the sources as a **hard gate**, and each blocks
something the sprint plan already schedules.

| # | Gate | Status | Blocks |
|---|---|---|---|
| 23 | Synthetic test data pipeline | Not started | Offshore development beginning — Week 1 |
| 24 | Offshore DLP controls | Not started | Offshore receiving **any** environment access — Week 1 |
| 25 | Offshore contractor registry | Pending, marked *"Immediately"* | — |
| 26 | Break-glass access management system | Not started | Provisioning any production environment |
| 27 | NIST SP 800-171 gap assessment (110 requirements) | Not started | Provisioning any production environment |
| 28 | DR plan — annotated in its own source as *"This is completely fabricated. Need to discuss with Ed."* | Under assessment | First state production go-live |
| 29 | State DPA review for all 28 states | Pending | First state production go-live |
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#not-started-gates -->
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#open-items -->

Items 23 and 24 are the sharpest: both are stated as prerequisites for the offshore team
receiving access at all, and the plan has them starting in Week 1.
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#kickoff-gate -->

## Design questions the documents simply never answer {#unanswered}

| # | Question |
|---|---|
| 30 | **What is the demo state's specific workflow customization?** The whole prototype narrative turns on demonstrating one real state customization, and it is TBD everywhere |
| 31 | **Which roles may clear an NDL PossibleMatch?** "A designated reviewer" is as specific as the corpus gets |
| 32 | **What status does a reinstated application land in** after a successful appeal — Approved, or back to Under Review? Explicitly flagged as undocumented by the journey author |
| 33 | **What are the field inventories for application sections 2–7?** Only section 1 is designed, and RF-17 requires the whole form as server metadata |
| 34 | **Is `PREAPPROVAL_1` in scope?** The legacy NSLP-only intermediate gate is what Iowa's documented "two-stage approval" actually is |
| 35 | **Should a sponsor see state-side actor names?** The mockups show "State Reviewer" and "State Administrator" in the sponsor's own Updated By column — a disclosure decision, not a UI detail |
| 36 | **What does row selection enable on the site list?** Checkboxes and select-all exist with no bulk action bar |
| 37 | **Is `Site.Eligibility` (Free/Reduced/Paid) real?** It is a per-*child* category shown as a per-site attribute. Probably a mockup shortcut; if it reaches the schema it produces an unpopulatable column |
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#unanswered -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#site-eligibility -->

## Lower-severity inconsistencies {#lower-severity}

Recorded in full at `knowledge/distilled/99-contradictions-and-open-questions.md`; listed here
so nobody re-discovers them one at a time. None blocks work today.

| # | Item |
|---|---|
| 38 | Rate-table year alignment is off by one in the worked ClaimLaws example (a December 2024 approval labelled SY2025 freezing the SY2025-26 rate) |
| 39 | Two full rate tables that agree only if you know they are different years — and synthetic seeding will use whichever an engineer opens first |
| 40 | The PY rollover job's firing date is given as July 1, October 1 and ~May 1 in a single document, with a cron expression that disagrees with its own comment |
| 41 | Domain count is 25, 28, 31 or 33 depending on the document |
| 42 | 1,402 tables is attributed to the legacy footprint in one document and to the greenfield target in another; the collapse arithmetic does not close either |
| 43 | "Database-per-tenant" and "schema-per-tenant" are used interchangeably — the intent is settled, the vocabulary is not, and they cost differently |
| 44 | The environment model is "all ephemeral except production" in one document and persistent shared dev/staging in two others — a large DevOps scope difference on a 40-hour estimate |
| 45 | The Secrets Manager path convention appears in three different shapes, and path shape is load-bearing for IAM policies |
| 46 | Sprint numbering is offset by one between the feature list and the sprint plan — always cite weeks |
| 47 | Sprint 2 is dated "August 31–September 1", a two-day sprint, in both plans |
| 48 | .NET 8 everywhere except one line specifying ASP.NET Core 10 |
| 49 | FNS-44 appears as "NA-44" and "FNA-44" despite the explicit rule that report numbers are unchanged |
| 50 | SMP (Special Milk Program) is absent from the canonical program list but present in three other places, including a live Formly field condition |
| 51 | Rate management is "Phase 2" in one document and an already-exercised Phase 1 proof-of-concept in two others |
| 52 | `LateClaimCutoffDays = 6` appears as the platform default in two documents where every other reference says 60 |
| 53 | Which design system — `@linq/snackpaq` (RF-46, premised on reuse) or the delivered "Public Trust Modern" spec? Materially affects a 64-hour estimate |
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#rate-year-offset -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#rollover-date -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#tenancy-terminology -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#environment-model -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#secret-path-shape -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#design-system -->

## Raised by the newest document {#new-conflicts}

| # | Question | Why it matters |
|---|---|---|
| 54 | **Characterization tests against a legacy stored procedure the team cannot see.** Phase 1 test scope requires *"≥ 80% branch coverage"* against the legacy SNP approval procedure — while offshore has zero legacy access, several procedures are deliberately encrypted, and replay validation is scoped as onshore-only work outside the prototype | An 80% coverage target against unavailable source is not a plan. Is this onshore work inside the window, or aspirational? |
| 55 | **Phase 1 surface is larger in the architecture than in the feature list.** Notification Service, Audit Timeline query API, Snowflake account, Tenant Registry, Federal Report Engine contracts, Rules Engine scaffold, `cnp_ext`, Terraform, AWS CodeDeploy, per-PR ephemeral environments, Playwright, and a per-state migration runner all appear with no RF number and no hours | Individually small; collectively a different Phase 1 against a fixed 2,264-hour estimate |
| 56 | **`EntitySnapshots` — prior state, or state at the transition?** The architecture says *"full prior-state JSONB"*; every other source says the snapshot is taken *at* the transition | Determines whether "what did this look like the day it was approved" is answered by the approval row or the next one. Not a nuance in an audit table |
| 57 | **Does `IsFederal` also live on `FormField` and `ComplianceRuleDef`?** The architecture names six carriers; ADR-007 names four | A federally mandated form field a state cannot hide is a genuinely useful idea that appears nowhere else — and would be an unscheduled schema column plus a write-time check |
| 58 | **Is the Phase 1 permission seed ~25, 68, ~180 or 415?** The architecture adds a fourth figure for the SECURITY domain seed | SECURITY is the only domain Phase 1 migrates, so its size *is* the sprint scope |
| 59 | **`TenantRegistry`** — platform version and active features per state — appears only in the newest document | If real, it is a new `cnp_global` table plus an admin API, currently in no data model |
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#characterization-access -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#phase-1-surface -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#snapshot-timing -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#isfederal-carriers -->
<!-- from: knowledge/distilled/99-contradictions-and-open-questions.md#permission-seed-count -->
<!-- from: knowledge/distilled/13-foundational-architecture.md#f-tenant -->

Two further documents are now known to exist and are not supplied: **the Synopsis** (a fifth
structural taxonomy of the platform — five blocks, alongside the four tiers, four layers and
three configuration layers) and **the v0.2 proposal**, whose Section 5.3 defines the onboarding
test that is effectively the foundation's Definition of Done.
<!-- from: knowledge/distilled/13-foundational-architecture.md#missing-refs -->

## Assumptions this context makes {#assumptions}

Stated explicitly so they can be challenged rather than inherited.

1. **The eight FRDs and the 51-feature list are the authoritative statement of Phase 1 scope**,
   and the six screens represent a broader product vision from which Phase 1 takes a subset.
   This is an inference from the FRDs' explicit scope statements, not something any document
   says. If it is wrong, items 4, 5 and 6 above become much larger than open questions.
2. **The demo state is Iowa.** Inferred from the screens and the supplied Iowa legacy analysis;
   no design document says so.
3. **"Public Trust Modern" is a theme for snackpaq rather than a replacement**, because its
   tokens map cleanly onto the CSS-custom-property mechanism the frontend architecture already
   describes. Unverified.

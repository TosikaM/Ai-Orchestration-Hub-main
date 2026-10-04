# Data architecture

## The two-database split {#split}

| | `cnp_global` | `cnp_ops` |
|---|---|---|
| What it is | One shared cluster, one schema | One cluster, one schema per state |
| Contains | Federal codes, rates, program definitions, workflow state machines, RBAC catalog, form/review engine catalogs | All operational data: sponsors, sites, applications, claims, enrollments, audit logs |
| Size | ~387 tables | ~1,015 tables per state schema |
| Owner | LINQ — no state can write here via the app | State agency data, isolated per state |
| Examples | — | `cnp_ops.ut`, `cnp_ops.wi`, `cnp_ops.me`, `cnp_ops.ak`, `cnp_ops.hi`, `cnp_ops.mo` |
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-1 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-2 -->

Everything ending in `*Types`, `*Codes`, `*Statuses`, plus `ProgramMealRates`,
`ReviewVersions`, `VCAScoringTools` and `AnnualFormTypes`, lives in `cnp_global`.
<!-- source: CSN-Data-140826-132933.md#page-3 -->

## The tenant boundary is the schema {#tenant-boundary}

**There is no `TenantId` column in Aurora.** The schema name *is* the tenant. Cross-state data
access is structurally impossible, not merely policy-controlled.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-6 -->

The rejected alternative and its failure mode is the whole argument: a shared schema with a
`TenantId` requires a row-level security filter on every query, and **a missing WHERE clause
exposes every state's data — the failure mode is silent and catastrophic.** Schema-per-tenant
makes that impossible at the database level regardless of application bugs.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-6 -->

Separate RDS clusters per state were also rejected: cost-prohibitive at 28 states, schema
migrations would need 28 independent pipeline runs, and connection-pool overhead is
unacceptable.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-7 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-2 -->

Two consequences carried forward explicitly:

- **A DBA connected to the wrong schema sees the wrong state's data with no warning.**
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-2 -->
- Because it is one cluster with per-state schemas rather than separate clusters, a single
  Aurora cluster failure affects all states simultaneously — the DR runbook must cover
  restoring a single state schema from cluster-level PITR without affecting the others.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-16 -->

`TenantCode` exists in exactly one place: the CDC pipeline **adds** it during replication to
Snowflake, where all states are aggregated for analytics by design. This is correct and not
inconsistent with Aurora's isolation model.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-6 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-19 -->

> The corpus uses "database-per-tenant" and "schema-per-tenant" interchangeably for this
> design. See `99-contradictions-and-open-questions.md#tenancy-terminology`.

## Per-state deployment independence {#deployment-independence}

Because schemas are per-state, migrations are independent — described as a feature, not a
constraint:

- A migration failing for one state does not affect others.
- A state can be held at a prior schema version during its **SFSP operational blackout
  (May–August)** without blocking other states from receiving updates.
- New states onboard via the Tenant Onboarding API and then run the full migration sequence.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-11 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-7 -->

## The data spine {#spine}

`ProgramGroups → ProgramGroupYears → ProgramGroupEnrollments`. **Every Application and every
Claim FK-chains through `ProgramGroupYears`.** It is the universal join key across all domains.
<!-- source: CSN-Data-140826-132933.md#page-8 -->

Every piece of data has to answer two questions: which federal program is this for, and which
school year does it cover. The spine is the single source of truth for both.
<!-- source: CSN-Data-140826-132933.md#page-8 -->

| Table | Where | What |
|---|---|---|
| `ProgramGroups` | cnp_global | Master list of federal programs. Almost never changes |
| `ProgramGroupYears` | cnp_global | One row per program + year, with boundaries. Carries no operational state |
| `ProgramGroupEnrollments` | cnp_ops | One row per sponsor enrolled in a program year, with `StatusCode` and event history |
| `ClaimRateAmounts` | cnp_global | Federal reimbursement rates by program/meal type/eligibility category, effective-dated |
| `ProgramRatePeriods` | cnp_global | Per-program rate-period boundaries |
| `TenantProgramYearStatus` | cnp_ops | Each state's operational status for a program year |
<!-- source: CSN-Data-140826-132933.md#page-8 -->
<!-- source: CSN-Data-140826-132933.md#page-9 -->

### Program year boundaries {#program-years}

- **NSLP, SBP** — 1 July to 30 June (school year, e.g. SY2025-26)
- **CACFP** — 1 October to 30 September
- **SFSP** — seasonal, roughly May–September operating window; its *rate* cycle is 1 January
  to 31 December

This is **not** the Federal Fiscal Year (1 Oct – 30 Sep). The FFY governs federal funding
allocations and FNS reporting; it should not appear in `StartDate`/`EndDate` for school
nutrition programs.
<!-- source: CSN-Data-140826-132933.md#page-8 -->
<!-- source: CSN-Data-140826-132933.md#page-9 -->

`ProgramRatePeriods` exists because a single effective date on `ClaimRateAmounts` cannot
represent both the SFSP January–December cycle and the July–June cycle used by NSLP/SBP/CACFP.
Its secondary use is mid-year rate adjustments (as happened in January 2022 for COVID relief):
close the current period's `EndDate` and insert a new row. It is intentionally decoupled from
`ProgramGroupYears.StartDate/EndDate` — a CACFP program year running October–September will
have rate-period rows starting 1 July, which predates the program year itself. **This is
correct by design.**
<!-- source: CSN-Data-140826-132933.md#page-9 -->
<!-- source: CSN-Data-140826-132933.md#page-10 -->

`TenantProgramYearStatus` (`Open | ClaimsLocked | YearEndProcessing | Closed | RolledOver`)
tracks each state's close-out independently — state A may close SY2025-26 in August while
state B is still processing September claims. **The rollover job and claim submission cutoff
logic read this table, not `ProgramGroupYears`.**
<!-- source: CSN-Data-140826-132933.md#page-9 -->
<!-- source: CSN-Data-140826-132933.md#page-10 -->

### The four problems the spine solves {#spine-rationale}

1. **Join consistency.** If Claims stores `programCode = 'NSLP'`, Applications stores `'SNP'`
   and a legacy table stores `'9'`, they cannot be joined reliably. A stable integer FK makes
   joins exact.
2. **Year-boundary logic stops being application code.** `WHERE pgyr.StartDate <= @claimDate
   AND pgyr.EndDate >= @claimDate` instead of every query knowing the boundary.
3. **Rate changes stop being risky.** The spine structurally separates the effective-dated
   rate lookup from the frozen eligibility snapshot applied to a specific claim.
4. **Multi-program sponsors become queryable.** One sponsor, three enrollment rows, rather
   than three sponsor rows or a comma-separated list.
<!-- source: CSN-Data-140826-132933.md#page-12 -->
<!-- source: CSN-Data-140826-132933.md#page-13 -->

## Domain tiers {#tiers}

Four authority tiers with explicit boundaries between them:

1. **Authoritative** — hold legal, financial and enforcement authority. Claims &
   Reimbursement, Accounting & Disbursement, Compliance & Administrative Review, Eligibility &
   Direct Certification. *Nothing below this line decides money, eligibility or enforcement.*
2. **Foundational/Supporting** — constrain inputs, never decide outcomes. Identity & Access,
   Configuration & Tenant, Sponsor & Site Registry, Applications & Agreements, Program Registry
   (the spine).
3. **Operational/Specialist** — own program rules and integration surfaces. Program domains
   (SNP, CACFP, DCH, SFSP, FFVP, SSFO, CEP), modules, platform services.
4. **Observational** — read models and outbound services only. Reporting & Analytics
   (→ Snowflake), Audit & Observability, Notifications, Communications, Reference Data,
   LaunchDarkly. *Consumes facts; never influences behaviour.*
<!-- source: CSN-Platform Domains-140826-133136.md#page-1 -->
<!-- source: CSN-Data-140826-132933.md#page-1 -->

> The number of domains is reported as 25, 28, 31 and 33 in four different documents. See
> `99-contradictions-and-open-questions.md#domain-count`.

## Approximate domain sizes {#domain-sizes}

Compliance & Administrative Review ~375 · Accounting & Finance 147 · Eligibility & Direct
Certification 147 · Applications & Agreements ~173 · Food Distribution 128 · Sponsor & Site
Registry ~121 · Claims & Reimbursement 85 · Identity & Access ~79 · Communications & Email ~75
· CACFP ~58 · SNP/NSLP ~48 · DCH ~42 · Configuration & Tenant ~35 · SFSP ~33 · Documents &
Attachments ~33 · FTP & Integration ~31 · Reporting & Analytics ~28 · Workflow & Tasks ~25 ·
Budget ~19 · Audit & Observability ~18 · SSFO ~16 · VCA Checklist ~16 · Reference Data ~12 ·
LaunchDarkly ~8 · Waivers ~7.
<!-- source: CSN-Data-140826-132933.md#page-13 -->
<!-- source: CSN-Data-140826-132933.md#page-14 -->
<!-- source: CSN-Data-140826-132933.md#page-20 -->
<!-- source: CSN-Data-140826-132933.md#page-31 -->
<!-- source: CSN-Data-140826-132933.md#page-34 -->
<!-- source: CSN-Data-140826-132933.md#page-37 -->
<!-- source: CSN-Data-140826-132933.md#page-41 -->
<!-- source: CSN-Data-140826-132933.md#page-45 -->
<!-- source: CSN-Data-140826-132933.md#page-47 -->

Compliance is ~375 tables because *"the USDA requires state agencies to collect extremely
specific evidence for each type of finding, and each finding type has its own data
structure"* — a CACFP centre meal observation form has different fields from a DCH one; a
five-day production reconciliation differs from a milk audit. Each needs its own detail, error,
status and summary table, multiplied across programs and finding categories.
<!-- source: CSN-Data-140826-132933.md#page-20 -->

## Deliberate schema isolation for Serious Deficiency {#serdef}

`SeriousDeficiency` lives in a **separate `[serdef]` schema** for regulatory reasons: when USDA
regulations require a state agency to initiate serious deficiency proceedings, that
documentation must be legally defensible on appeal. A separate schema creates a clean audit
boundary so no other domain's queries can accidentally modify SerDef records, and supports the
requirement that SerDef records be immutable once issued.
<!-- source: CSN-Data-140826-132933.md#page-24 -->

## The table collapse and its costs {#collapse}

Roughly 840 of the legacy CTS tables were absorbed into roughly 25 greenfield tables. The
"Keep" tables represent distinct data concepts that could not be collapsed further.

| Collapse | Before → After | Mechanism |
|---|---|---|
| LookupCodes | 353 → 1 | One table per code list becomes a category of rows in `LookupCodes` |
| Review Engine | 188 → 7 | Form variation modelled structurally becomes data rows |
| Form Engine | 99 → 10 | Same pattern for application forms, site worksheets, budgets, renewals |
| RBAC | ~20 tables + 5,000+ ACL rows → 6 | Role-based permissions with tenant-level overrides |
| Eliminated | 180 → 0 | Temp, shuffle, version-tracking tables and CTS deployment artifacts |
<!-- source: CSN-Data-140826-132933.md#page-48 -->
<!-- source: CSN-Data-140826-132933.md#page-49 -->

**Four costs are stated honestly and should be treated as accepted risks, not surprises:**

1. **Referential integrity moves to the API layer.** With everything collapsed into
   `LookupCodes`, `SiteApplications.SiteTypeCode → SiteTypes.SiteTypeCode` can no longer be
   expressed in DDL. `FormFieldValues` stores all values as TEXT, cast at read time. **If the
   API has a bug, invalid data gets in with no database-level backstop.**
2. **`FormFieldValues` and `ReviewAnswers` become the largest tables in the system** — every
   form instance × every field. The indexing strategy must be designed before build, not
   retrofitted when it slows down.
3. **Reporting complexity increases significantly.** Queries trivial in CTS ("show all sites
   that answered Yes to question X") become multi-join **EAV** lookups. Whoever writes the
   reporting layer needs to know they are working against an EAV model, not typed columns.
4. **The 180 eliminated tables need dependency verification.** The risk is CTS stored
   procedures or scheduled jobs referencing them — an explicit onshore task before anything is
   dropped, because the offshore team has zero access to the existing codebase.
<!-- source: CSN-Data-140826-132933.md#page-48 -->
<!-- source: CSN-Data-140826-132933.md#page-49 -->

## Per-state extension schemas {#extensions}

Genuinely unique state needs live in a `cnp_ext` schema within the same cluster, never in
shared platform code. Known cases requiring decisions before Phase 3:

- **Ohio** — 42-table budget extension, plus `fdp` and `gratefdp` schemas
- **Wyoming** — `fdp` and `gratefdp` (shared structure with Ohio, cannot be separated without
  schema surgery)
- **Iowa** — `fnm` schema
- **Hawaii** — Professional Standards tables (USDA-mandated, unique to Hawaii)
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-3 -->
<!-- source: CSN-Platform Domains-140826-133136.md#page-8 -->

## The per-state adapter pattern {#adapters}

Addresses the failure mode *"state-specific behaviour had no clean home."* **Every state
difference is a flag, an adapter, a config value, or a separate extension schema — no domain
anywhere contains a branch on which state it is running.** Four adapter interfaces only:

| Interface | Purpose | Known implementations |
|---|---|---|
| `IAccountingExporter` | State accounting system export | UT→USAS · CO→COFRS · SC→CALSTARS · MT→SABHRS · TN→ISAS · OH→SCEIS |
| `IDcFeedAdapter` | Per-tenant DC source config (SNAP, Medicaid, TANF, FDPIR); PGP/SFTP or REST | UT: Medicaid+SNAP · IN: SNAP+Medicaid+TANF+DCS |
| `IEdFiAdapter` | Student information systems | `RestEdFiAdapter` where an Ed-Fi ODS exists, `FlatFileEdFiAdapter` fallback |
| `ILicenseAdapter` | Per-state childcare provider licence verification | UT→DOPL licence sync |
<!-- source: CSN-Platform Domains-140826-133136.md#page-6 -->
<!-- source: CSN-Platform Domains-140826-133136.md#page-8 -->
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-6 -->

## Analytics: the CDC pipeline {#cdc}

AWS DMS runs continuous Change Data Capture from every `cnp_ops` Aurora instance to Snowflake
— one agent per instance, capturing the binary log — through an S3 staging bucket, Snowpipe
auto-ingest, into a `cnp_analytics` landing schema that mirrors the operational schema with
added metadata (`cdc_timestamp`, `source_state`, `operation_type`). Curated reporting views
over that schema are the stable API FNS reports and dashboards depend on.

`cnp_global` tables replicate on a **nightly full refresh** rather than CDC, since they change
infrequently and the volume is small.
<!-- source: CSN-Data-140826-132933.md#page-39 -->
<!-- source: CSN-Data-140826-132933.md#page-40 -->

The separation exists because *"a query that takes 45 seconds to build a federal summary would
block a claim approval for 45 seconds."* The operational database records transactions;
Snowflake answers questions about them. **Nothing in this domain writes back.** The
consequence is that reporting infrastructure can be rebuilt or replaced without touching a
single operational table.
<!-- source: CSN-Data-140826-132933.md#page-37 -->

## Federal reports generated {#federal-reports}

| Report | What | Cadence |
|---|---|---|
| FNS-10 | School Program Operations Report — meal counts by program, meal type, eligibility category, by sponsor and site | Monthly |
| FNS-44 | CACFP participation — the CACFP equivalent of FNS-10, by institution type | Monthly |
| FNS-418 | SFSP participation, by site type and service mode | At program close |
| FNS-640 | Administrative Review Information — reviews conducted, findings, fiscal actions assessed and recovered, SerDef proceedings, review-cycle compliance | Annual |
| FNS-905 | Direct Certification and Verification Summary — DC certifications by source, DC rate, verification sample and outcomes, error rate | Annual |
| FNS-777 | Financial Status Report — grant drawdowns, expenditures, unexpended balances; Section 4/11 split | Monthly |
<!-- source: CSN-Data-140826-132933.md#page-40 -->
<!-- source: CSN-Data-140826-132933.md#page-41 -->
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-5 -->
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-7 -->

FNS-640 and FNS-905 both feed the compliance risk-scoring model as well as the federal
submission — the same views, one source of truth.
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-8 -->

## NLP analytics is template-based, not text-to-SQL {#nlp-analytics}

The LLM maps a natural-language question to a template ID in `ApprovedQueryTemplates` and
extracts parameters. **It does not generate SQL.** `TenantCode` is injected from the
authenticated session, never from the user's question. Unmatched questions are rejected with
an explanation of what is supported. Every attempt is logged in `QueryLog` including a
`CrossTenantFlag`.

Arbitrary text-to-SQL was rejected because *"arbitrary SQL generation over a multi-state
warehouse has no reliable way to prevent a cleverly phrased question from returning another
state's data."* Low-count suppression (fewer than 5 individuals) applies to results, to
prevent statistical re-identification of children's eligibility status — required for FERPA
and particularly for small-population states.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-10 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-11 -->

## Data-model requirements to enforce {#hard-requirements}

- **Every financial column is `DECIMAL(18,2)`.** No FLOAT, no REAL, no NUMERIC without
  explicit precision. A migration or data-fix script casting a financial value to float is a
  bug that must be rejected.
- **Audit tables are partitioned from day one** (monthly or yearly). Retrofitting partitioning
  after they hold production data is expensive. Minimum index
  `(EntityType, EntityId, CreatedAt)`; GIN index on `EntitySnapshots.DataJson` if content
  queries are expected.
- **DC feed staging tables need a unique index on `SourceRowHash CHAR(64)`** (SHA-256 of the
  raw row bytes) per state schema, to prevent duplicate ingestion on retries.
- **Connection pooling must be per-schema**, not one shared pool — at 28 states the `cnp_ops`
  cluster sees 28 distinct connection strings.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-3 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-4 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-17 -->

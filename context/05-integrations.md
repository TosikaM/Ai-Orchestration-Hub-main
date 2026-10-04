<!-- PROJECT CONTEXT — synthesised, not a source document.

     Every factual claim here needs a provenance comment naming where it came from:
         <!-- from: knowledge/distilled/<topic>.md#<anchor> -->
     `python scripts/project-context.py check` fails on a claim without one.

     If a statement has no source, it is an ASSUMPTION. Move it to 06-open-questions.md
     with the assumption stated, rather than leaving it here where the next reader will
     take it for a requirement. -->

# Integrations

## The governing rule {#adapter-rule}

**No domain anywhere contains a branch on which state it is running.** Every state difference is
a feature flag, an adapter, a config value, or a separate extension schema. This exists to fix a
named legacy failure mode — *"state-specific behaviour had no clean home"* — which is how
Missouri's federal report logic ended up 50% larger than Utah's for the same federal
requirement.
<!-- from: knowledge/distilled/05-data-architecture.md#adapters -->
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#legacy-failure-modes -->

**There are exactly four adapter interfaces.** A new state-specific behaviour must fit one of
them or be a config value; it does not get a fifth slot without a design decision.
<!-- from: knowledge/distilled/05-data-architecture.md#adapters -->

## In Phase 1 {#phase-1}

| System | Purpose | Phase 1 status |
|---|---|---|
| **Identity provider (OIDC)** | Real SSO, per-state realm, JWT carrying roles + tenant scope | **In scope, provider undecided** |
| **AWS Secrets Manager** | Every credential, via `ISecretProvider` | In scope |
| **ElastiCache (Redis)** | Config resolution cache, three TTL tiers, cache-bust endpoint | In scope |
| **LaunchDarkly** | Module-level feature flags | In scope — ~5 flags for the prototype |
| **USDA FNS NDL lookup** | Federal disqualification screening | **Stub / synthetic dataset**; blocking behaviour and audit are real |
| **S3** | Form PDF snapshots, presigned URLs | In scope |
| **Hangfire** | Background jobs, PostgreSQL-backed | Registered; the PY rollover job is not required to fire |
<!-- from: knowledge/distilled/09-infrastructure-and-environments.md#stack -->
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#ndl-phase-1 -->

## Deferred beyond Phase 1 {#deferred}

| System | Purpose | Interface |
|---|---|---|
| **State benefit agencies (SNAP, Medicaid, TANF, FDPIR)** | Nightly Direct Certification feeds | `IDcFeedAdapter` |
| **State accounting systems** | Payment and grant drawdown export | `IAccountingExporter` |
| **Student information systems** | Enrollment and demographic data | `IEdFiAdapter` |
| **State licensing systems** | Childcare provider licence verification | `ILicenseAdapter` |
| **Snowflake** | Cross-state analytics via CDC | AWS DMS pipeline |
| **Federal Register API** | Daily monitoring for rate and policy publications | Phase 2 AI layer |
<!-- from: knowledge/distilled/05-data-architecture.md#adapters -->
<!-- from: knowledge/distilled/05-data-architecture.md#cdc -->

Known implementations, useful because they show the shape of state variation:

| Adapter | Known per-state implementations |
|---|---|
| `IAccountingExporter` | UT→USAS · CO→COFRS · SC→CALSTARS · MT→SABHRS · TN→ISAS · OH→SCEIS |
| `IDcFeedAdapter` | UT: Medicaid + SNAP · IN: SNAP + Medicaid + TANF + DCS |
| `IEdFiAdapter` | `RestEdFiAdapter` where an Ed-Fi ODS exists; `FlatFileEdFiAdapter` fallback |
| `ILicenseAdapter` | UT→DOPL licence sync |
<!-- from: knowledge/distilled/05-data-architecture.md#adapters -->

## Direct Certification feeds — the operationally hardest integration {#dc-feeds}

Transport and encryption vary per state. The adapter is registered in `cnp_global`; **credentials
live in Secrets Manager only.**

| State | Transport | Capabilities |
|---|---|---|
| Indiana | SFTP + PGP, download only | `SftpDownload`, `PgpDecrypt` |
| Hawaii | SFTP + ZIP, bidirectional | `SftpDownload`, `SftpUpload`, `ZipUnwrap`, `ZipWrap` |
<!-- from: knowledge/distilled/09-infrastructure-and-environments.md#dc-feeds -->

Rules that will otherwise be discovered the hard way:

- **Sessions must not be held open across long-running operations.** Open, complete, disconnect.
  Hawaii's bidirectional flow uses two separate sessions — do not hold the download session open
  while staging and matching runs.
- **On auth failure, invalidate the Secrets Manager cache and retry once with a fresh
  credential. Never re-cache a failed credential** for the process lifetime.
- **PGP passphrases are `char[]`, not `string`**, so they can be zeroed after use.
- Decryption writes to a temp directory only, cleaned up immediately after parsing.
- Staging tables need a **unique index on `SourceRowHash CHAR(64)`** per state schema, so a retry
  cannot double-ingest.
<!-- from: knowledge/distilled/09-infrastructure-and-environments.md#dc-feeds -->
<!-- from: knowledge/distilled/05-data-architecture.md#hard-requirements -->

**LINQ does not control DC credential rotation — the state benefit agency does.** The
coordinated process: the agency gives at least 24 hours notice → the onshore config team
receives the credential through a **secure out-of-band channel, not email** → onshore updates
Secrets Manager via the DC Feed Adapter API → the next nightly load picks it up → onshore
confirms success and the agency retires the old credential. **No deployment for any rotation.**
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#rotation -->

## Analytics: the CDC pipeline {#cdc}

AWS DMS streams every INSERT, UPDATE and DELETE from each `cnp_ops` Aurora instance to
Snowflake — one agent per instance → S3 staging → Snowpipe → a `cnp_analytics` schema mirroring
the operational schema with `cdc_timestamp`, `source_state` and `operation_type` added. Curated
views over that schema are the stable API reports depend on. `cnp_global` replicates on a
**nightly full refresh** instead, since it changes rarely.
<!-- from: knowledge/distilled/05-data-architecture.md#cdc -->

**This is the only place `TenantCode` exists as a column.** The pipeline adds it during
replication, because the warehouse aggregates all states by design.
<!-- from: knowledge/distilled/05-data-architecture.md#tenant-boundary -->

**Nothing in this domain writes back.** The operational database records transactions; Snowflake
answers questions about them. The reason is concrete: *"a query that takes 45 seconds to build a
federal summary would block a claim approval for 45 seconds."*
<!-- from: knowledge/distilled/05-data-architecture.md#cdc -->

## Federal reporting {#federal-reports}

| Report | What | Cadence |
|---|---|---|
| FNS-10 | School program operations — meal counts by program, meal type, eligibility category | Monthly |
| FNS-44 | CACFP participation — the CACFP equivalent of FNS-10 | Monthly |
| FNS-418 | SFSP participation by site type and service mode | At program close |
| FNS-640 | Administrative review information — reviews, findings, fiscal actions assessed and recovered | Annual |
| FNS-905 | Direct certification and verification summary | Annual |
| FNS-777 | Financial status — grant drawdowns, expenditures, balances; Section 4/11 split | Monthly |
<!-- from: knowledge/distilled/05-data-architecture.md#federal-reports -->

**Report numbers are unchanged by the FNS→FNA agency rename** (effective 1 June 2026). Federal
Register publications now say "FNA"; the report codes stay FNS-*.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#fns-to-fna -->

All out of scope for Phase 1.
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#out-of-scope -->

## Natural-language analytics — template-based, never text-to-SQL {#nlp}

The LLM maps a question to a template ID in `ApprovedQueryTemplates` and extracts parameters.
**It does not generate SQL.** `TenantCode` is injected from the authenticated session, never from
the user's question. Unmatched questions are rejected with an explanation of what is supported;
every attempt is logged with a `CrossTenantFlag`.

Arbitrary text-to-SQL was rejected because *"there is no reliable way to prevent a cleverly
phrased question from returning another state's data."* Low-count suppression (fewer than 5
individuals) applies to results, for FERPA and particularly for small-population states.
<!-- from: knowledge/distilled/05-data-architecture.md#nlp-analytics -->

Phase 2. Every AI output requires human review before any platform action.
<!-- from: knowledge/distilled/05-data-architecture.md#nlp-analytics -->

## External data the platform reads but does not own {#external-data}

Knowing which fields these are matters for distinguishing a bug from correct read-only
behaviour.

| Data | Source | Mechanism | Freshness | Who corrects it |
|---|---|---|---|---|
| Addresses (Iowa) | Iowa's Enterprise Information System (EIS) | Database synonym / linked read | Nightly refresh | State EIS team |
| County codes | State reference database | API call | On demand | State GIS/Admin |
| Reimbursement rates | USDA + state amendments | Manual entry after publication | Before each fiscal year | State Finance |
| Organisation tax IDs | State business registration | File transfer | Weekly batch | State Secretary of State |
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#external-sources -->

If Iowa is the demo state, **the five address fields on screen 4 are read-only and
state-sourced**, and no design exists for how that is communicated to the sponsor.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-4 -->

## Configuration API surface {#config-api}

Six API families exist so that per-state behaviour is operated rather than deployed: CnpDefaults,
Workflow Override, Feature Flag, DC Feed Adapter, Accounting Export Adapter, and Tenant
Onboarding. Every endpoint requires an authenticated onshore admin JWT, all writes are logged to
`FieldChangeLog`, and **no endpoint allows overriding a federal-locked value.**
<!-- from: knowledge/distilled/03-configuration-model.md#deploy-vs-config -->
<!-- from: knowledge/distilled/03-configuration-model.md#onboarding -->

The stated test of the whole boundary: **can a new state agency be onboarded without a code
deployment?** The answer should be yes for everything except genuinely novel requirements.
<!-- from: knowledge/distilled/03-configuration-model.md#onboarding -->

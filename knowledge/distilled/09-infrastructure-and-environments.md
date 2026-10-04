# Infrastructure, environments and the technology stack

## The stack {#stack}

| Layer | Technology | Notes |
|---|---|---|
| Frontend | **Angular 17+**, LINQ `@linq/snackpaq` design system, Angular Formly | Net-new repo, seeded from the Shared Services Starter Angular project. Responsive, desktop priority for demo. No IE support required |
| API | **.NET 8**, MediatR (CQRS), FluentValidation | One API project. **No microservices for the prototype.** Commands and Queries organised by domain subfolder, not flat |
| Database | **Aurora PostgreSQL** — `cnp_global` + `cnp_ops` schema per state | |
| Cache | Amazon ElastiCache (Redis) | Three-tier TTL per config key; cache-bust endpoint required |
| Secrets | AWS Secrets Manager via `ISecretProvider` | No credentials in code, config files or environment variables — hard rule |
| Background jobs | Hangfire, PostgreSQL backing store | PY rollover job registered but not required to fire for the prototype |
| Infrastructure | AWS ECS Fargate, ALB, VPC | Single region (us-east-1). No multi-region until the DR plan is finalized |
| CI/CD | GitHub Actions | Deploy to staging on merge to main; deploy to demo on tag |
| Migrations | **FluentMigrator or EF Core Migrations — decision pending** | Per-schema. `cnp_global` runs once; `cnp_ops.{state}` runs per state |
| DB triggers | PostgreSQL PL/pgSQL | `IsFederal` enforcement on the two override tables |
| Feature flags | LaunchDarkly | Module-level flags only for the prototype; ~5 flags needed |
| Analytics | Snowflake | CDC target for cross-state analytics |
<!-- source: CSN-Prototype-140826-133159.md#page-3 -->
<!-- source: CSN-Prototype-140826-133159.md#page-4 -->
<!-- source: CSN-Prototype-140826-133159.md#page-5 -->

Architectural shape: a **modular monolith** — a single ECS Fargate container running an
ASP.NET Core 8 application, with an Angular frontend and Aurora PostgreSQL.
<!-- source: NextGenOverviewEngineering.md#slide-6 -->

### Why a monolith, deliberately {#monolith}

*"Wrong boundaries cost more in microservices."* In a monolith a wrong boundary is a namespace
rename and moving classes; in microservices it is a new API contract, a data migration and
distributed transaction complexity. **Boundaries are a hypothesis** — the domain lines were
drawn carefully but may not survive contact with real usage, and a monolith allows adjusting
them before they are locked into service contracts.

Every domain is *already* isolated by namespace and database schema, so services can be
extracted when evidence says to. The four authoritative domains — Claims, Accounting,
Compliance, Eligibility — are named as the most likely first candidates.
<!-- source: NextGenOverviewEngineering.md#slide-5 -->
<!-- source: NextGenOverviewEngineering.md#slide-13 -->

### Enforced code structure {#code-structure}

- MediatR folder structure `/src/Commands/{Domain}/` and `/src/Queries/{Domain}/` — **not a
  flat `Commands/` dump.** Prototype domains: Applications, Workflow, Config, Rights.
- **DTOs required at the API boundary.** No EF Core entity or DB model object crosses the API
  boundary to a consumer. Reviewed by the offshore backend lead before Sprint 3.
<!-- source: CSN-Prototype-140826-133159.md#page-3 -->
<!-- source: CSN-Prototype-140826-133159.md#page-10 -->
<!-- source: CSN-Prototype-140826-133159.md#page-11 -->

## Required AWS services {#services}

Aurora PostgreSQL (private subnets only) · ElastiCache Redis (config resolution cache;
general config propagation under 5 minutes) · ECS Fargate (API + Angular task definitions) ·
Application Load Balancer (HTTPS termination, valid certificate for demo and prod domains) ·
Secrets Manager (paths documented and provisioned **before any service deploys**) · S3 (form
PDF snapshots, presigned URLs, encryption at rest, versioning enabled, **no public access**) ·
Snowflake (CDC target) · VPC (private subnets for Aurora, Redis and ECS) · GitHub Actions ·
LaunchDarkly (environments matching dev, staging, UAT, demo, prod).
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-7 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-8 -->

The Infrastructure document flags §3.1 as *"a discussion starting point. We will want
recommendations here based on organizational standards"* — so the service list is not yet
ratified against LINQ platform standards.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-7 -->

## Environments {#environments}

The stated target model is **all ephemeral except production** — non-production environments
are spun up on demand by the CI/CD pipeline or an operator trigger and torn down when no
longer needed. No environment is kept running idle.

| Environment | Lifecycle | Purpose | Notes |
|---|---|---|---|
| Dev | On-demand per engineer | Individual feature development | Synthetic data only. Offshore engineers have access |
| Test | On-demand per PR/branch | Automated integration testing | Created on PR open, torn down on close/merge |
| Staging | On-demand per release candidate | Pre-release validation | Full state migration run. Synthetic only |
| UAT | On-demand per UAT cycle | State agency or internal sign-off | Sanitized seed data. **Separate Aurora cluster per spin-up** |
| Demo | On-demand per demo event | Sales / stakeholder demonstrations | Stable seed data. **No uncontrolled deploys during a live demo window** |
| Production | **Persistent** | Live state data | Onshore only. Break-glass for any direct access. Never torn down |
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-8 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-9 -->

> The Phase 1 feature list and sprint plan describe persistent dev/staging on a shared Aurora
> cluster with dedicated clusters for demo and UAT, which is a narrower model than
> "all ephemeral." See `99-contradictions-and-open-questions.md#environment-model`.

### What on-demand provisioning requires {#provisioning}

Every resource must be scripted; **manually provisioned resources are blockers** because they
break the automation model. Aurora cluster or schema, Secrets Manager path seeding, ECS task
definitions, ALB and DNS, LaunchDarkly environment, Redis, S3 buckets/prefixes — each with a
defined teardown.

The sharpest operational note: *"An environment without its Secrets Manager paths cannot
start. The seed script must run before the ECS tasks are registered. If any path is missing,
the service will fail to boot and the failure message will expose which secret name was
missing. Write the seed script before standing up any environment."*
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-9 -->

## Environment isolation from existing LINQ systems {#isolation}

All environments are **new AWS accounts and resources provisioned specifically for this
project.** None are connected to any existing LINQ system, database or infrastructure.
Offshore engineers have no path to any existing LINQ system, at any point.
<!-- source: CSN-Prototype-140826-133159.md#page-6 -->
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->

## Deployment rules {#deployment}

- Migrations run **per schema**: `cnp_global` once per deployment; `cnp_ops.{state}` per state,
  each migrating independently.
- The `cnp_migration` role is used exclusively during migrations, provisioned only in CI/CD.
- Build → test → deploy to staging on PR merge; deploy to demo on tag. Every demo deploy is
  approved by the onshore tech lead.
- **Multi-region is not live.** Cross-region backup replication is configured (primary
  us-east-1, secondary us-west-2) but active failover is not, pending the DR plan.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-11 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-10 -->
<!-- source: CSN-Prototype-140826-133159.md#page-7 -->

## Direct Certification feed infrastructure {#dc-feeds}

Each participating state sends student eligibility data through a per-state adapter; transport
and encryption vary by state. The adapter is registered in `cnp_global`; **credentials live in
Secrets Manager only.**

| State | Transport | Capabilities |
|---|---|---|
| Indiana | SFTP + PGP (download only) | `SftpDownload`, `PgpDecrypt` |
| Hawaii | SFTP + ZIP (bidirectional) | `SftpDownload`, `SftpUpload`, `ZipUnwrap`, `ZipWrap` |

**SFTP session rules:** sessions must not be held open across long-running operations — open,
complete the operation, disconnect immediately. Hawaii's bidirectional flow uses two separate
sessions; do not hold the download session open while staging and matching occurs. On auth
failure, invalidate the Secrets Manager cache and retry once with a fresh credential; do not
re-cache on failure.

**PGP:** private keys in Secrets Manager only — never config files, source code or environment
variables. Passphrases as `char[]`, zeroed after use. Decryption writes to a temp directory
only, cleaned up immediately after parsing.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-18 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-19 -->

## Performance and indexing requirements {#performance}

- **Audit tables partitioned from day one** — monthly or yearly. Minimum index
  `(EntityType, EntityId, CreatedAt)`; GIN on `EntitySnapshots.DataJson` if content queries are
  expected.
- **Config resolution index** on `TenantCode`, `ProgramCode` and `EffectiveDate` — the
  `COALESCE` across `ConfigDefinitions` and `TenantConfigOverrides` runs on every API request
  that reads config, and although the result is cached in Redis, cache misses must resolve
  quickly.
- **`FormFieldValues` sizing** — one row per field per form instance; across all states and
  claim seasons it becomes one of the largest tables. Index `(InstanceId, FieldCode)` and
  `(FieldCode, FieldValue)` should be designed before the first state reaches high claim
  volume.
- **EAV advisory** — `FormFieldValues` and `ReviewAnswers` store all values as TEXT with no
  type knowledge in the database. Filtering or aggregating on a field value requires multi-table
  joins against the field catalog. *"Ensure the reporting layer designers are aware of this
  pattern before report query work begins."*
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-16 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-17 -->

## S3 requirements {#s3}

Form PDF snapshots are the legal record; `EntitySnapshots` in Aurora is the machine-queryable
companion. **Forms are never served directly from Aurora** — presigned URLs are generated at
read time.

- Per-state isolation at the object key level at minimum, consistent with schema-per-tenant
- Document versioning enabled
- Encryption at rest (NIST SP 800-171 MP controls)
- No public access on any CNP bucket
- Bucket policy restricted to the platform ECS task role only — no cross-state prefix access
- **Presigned URL TTL must be bounded** — long-lived presigned URLs on federal child records
  create a compliance exposure

Because form snapshots contain child nutrition eligibility data, the S3 access policy must be
as restrictive as the Aurora schema access policy.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-17 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-18 -->

## Frontend bootstrap sequence {#frontend-bootstrap}

1. **Subdomain resolution** — Route 53 → CloudFront → ALB; YARP extracts the state from the
   Host header and resolves the TenantId.
2. **OIDC login** — Angular checks for a valid JWT in memory; if absent, redirects to the
   state's realm → state IdP → returns a JWT carrying `tenant_id`, roles and programs.
3. **Tenant config load** — `GET /api/tenant/config` reads from `cnp_global`; `ICnpContext`
   resolves the state's `cnp_ops` connection. Returns agency name, logo S3 URL, brand colour
   and the LaunchDarkly bootstrap payload.
4. **Brand tokens applied** — CSS custom properties set on `:root`; snackpaq components pick
   up the tenant brand automatically. No component code changes between states.
5. **LaunchDarkly bootstrap** — SDK initialised with tenant context; the bootstrap payload
   seeds all flags instantly with no extra network call.
6. **Nav and routes built** — route guards check flags; disabled modules have their routes
   removed and nav items hidden.
7. **Session Replay** — privacy mode mask-all by default; student PII elements carry an
   `ld-privacy-redact` attribute.
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-2 -->
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-3 -->

## Server-driven forms {#forms}

Program year is part of the URL path — `/:programYear/applications/:program/:formType` — which
allows concurrent tabs across different program years without session conflict. `tenantId` is
resolved via `ICnpContext` from the subdomain, **not** from the URL.

The server builds the schema: load the base `FormDefinition` from `cnp_global` → apply tenant
overrides from `cnp_ops` → apply program-year conditions → return `FormlyFieldConfig[]`.
Angular Formly renders it; required/hidden/conditional states come from config, with **no
if/else in the template**. `hideExpression` evaluates against the live form model, so toggling
"Does your sponsor use FSMC?" reveals the FSMC section instantly without a page reload.
Hidden fields are skipped by validation automatically.
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-3 -->
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-4 -->

Five field states: Required, Optional, Hidden (not in the DOM; value reset to null; skipped
entirely by validation), Read-Only (visible, not editable, **server still validates on
submit**), and Conditional.
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-7 -->
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-8 -->

## PDF strategy {#pdf}

Three paths, deliberately split by complexity:

1. **User-initiated print** — `window.print()` with print CSS hiding navigation, sidebars and
   action bars. No server component. Covers applications, budgets, management plans, claim
   summaries. *"Simplest — works in all browsers"* and covers the 90% case with zero
   infrastructure.
2. **Multi-page reports** — server-side rendering via **QuestPDF** in the Document Service, for
   federal reports, review reports and audit exports where print CSS is insufficient. Returns
   an S3 presigned URL with a 15-minute TTL.
3. **Automated status-change snapshots** — on `ApplicationSubmitted` / `ClaimLocked` /
   `ReviewClosed`, SQS triggers the Document Service → `IPdfRenderService` → an immutable S3
   snapshot.

**EvoPdf (the legacy commercial library) is not carried forward.** `IPdfRenderService` abstracts
both implementations, chosen at render time based on `ReportComplexity` metadata.
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-5 -->
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-6 -->

## Per-state branding {#branding}

Logos stored in S3 at `/{tenantId}/branding/logo.svg`, uploaded by state agencies through a
branding settings page, served via CloudFront with long cache-control headers. If no logo is
set, the LINQ default is shown. `TenantConfig` carries `agencyName`, `logoUrl`, `primaryColor`
and `tenantCode`, applied as CSS custom properties on `:root`.
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-8 -->
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-9 -->

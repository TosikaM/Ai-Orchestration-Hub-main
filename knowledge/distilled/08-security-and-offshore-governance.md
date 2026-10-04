# Security, data handling and the offshore/onshore boundary

## The delivery model {#model}

**Offshore builds the engine; onshore configures per-state behaviour.** This is stated as the
organising principle of the whole platform, and the access rules below follow from it.
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-3 -->
<!-- source: CSN-Code Deployment vs Configuration-140826-133128.md#page-1 -->

## What data this is {#data}

Child eligibility determinations (free/reduced/paid status from household income, SNAP, TANF,
FDPIR or Medicaid participation); Direct Certification match records including child name,
school and program participation; National Disqualified List matches; and sponsor/site
financial records.

Subject to **FERPA** when held by a school or district, **NIST SP 800-171** as Controlled
Unclassified Information, state-level privacy law across 28 states, and federal program
integrity requirements.
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-1 -->

**NIST SP 800-171** applies because child nutrition eligibility data qualifies as CUI when
created or handled in connection with a federal program — 110 requirements across 14 control
families, **including development and staging environments that use realistic data.**
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-1 -->

**FERPA**: LINQ is a "school official" when processing eligibility data on behalf of a district
or state educational agency. No disclosure to third parties without consent, strict access
controls, breach notification. State Data Processing Agreements must explicitly address FERPA
before any real student data is processed.
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-1 -->
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-2 -->

## The access matrix {#access-matrix}

Reproduced identically in three documents, which suggests it is settled.

| Role | Prod data | Staging | Dev | Prod credentials | Schema migrations |
|---|---|---|---|---|---|
| LINQ US onshore engineer | Read-only via break-glass | Full | Full | None | Via CI/CD only |
| LINQ onshore config admin | Config writes via API only (no direct DB) | Full | Full | dc-feed paths only | Via CI/CD only |
| **Offshore engineer** | **NONE — ever** | Synthetic data only | Synthetic data only | **NONE — ever** | Via CI/CD only |
| LINQ DBA (US-based) | Read-only by default; break-glass write | Full | Full | Full | Via CI/CD only |
| State agency administrator | Own state via app only | No | None | None | N/A |
| FNS Auditor | Read-only for assigned states via app | No | None | None | N/A |
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-2 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-12 -->
<!-- source: CSN-Prototype-140826-133159.md#page-2 -->

## Offshore hard rules {#offshore-rules}

Described explicitly as **structural controls, not policy statements**:

1. **Zero access to production** environments, databases, AWS accounts or Secrets Manager
   paths.
2. **Zero access to production credentials**, enforced by IAM roles that physically cannot
   reach production Secrets Manager paths — *"not just policy."*
3. **Staging environments reachable by offshore contain synthetic data only.** Column masking
   is *explicitly called out as insufficient* — re-identification risk is high for
   small-population states like AK, HI and ME.
4. **All PRs touching compliance logic** (IsFederal configuration, audit trail, federal math,
   named workflow hooks) require review and approval from a **US-based onshore engineer**
   before merge. Offshore engineers cannot self-approve compliance PRs.
5. **Offshore engineers cannot export data** from any LINQ environment. DLP controls must be
   active on all environments they can access.
6. **Individual named accounts only.** Shared credentials are prohibited.
7. **Access is revoked within 24 hours** of an engagement ending — and the engagement manager
   must notify access management, because *"a contractor's departure alone does not trigger
   automatic revocation."*
8. Offshore engineers working on **AI/ML components** work only against synthetic training
   data; real claim and application data used for model training must be processed by US-based
   staff in a US-based secure environment.
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-3 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-13 -->

Contractor vetting: all offshore contractors sign a data handling agreement referencing NIST
SP 800-171 and FERPA before receiving any access. Offshore teams touching federal compliance
logic must be identified to the LINQ security team — **a requirement that extends to
subcontractors of subcontractors.**
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-3 -->

## The offshore kickoff gate {#kickoff-gate}

Before the offshore team receives access to **anything**:

- AWS dev/staging environments provisioned
- Secrets Manager paths documented for all dev/staging environments
- Individual named accounts provisioned per engineer
- Design document package delivered
- **DLP controls deployed and verified**
- The GitHub repo exists and is isolated from all existing LINQ repositories
- The dev AWS account has **no VPC peering or connectivity to any existing LINQ account**

Onshore tech lead and DevOps both sign off. *"This is the offshore team's kickoff gate — they
do not begin until these are confirmed."*
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-13 -->
<!-- source: CSN-Prototype-140826-133159.md#page-9 -->

## Break-glass — a hard gate that does not exist yet {#break-glass}

> **The break-glass system does not exist.** Until it is built there is no sanctioned path for
> any engineer to access production data directly. **Build this before any production
> environment is provisioned.**
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-12 -->

When built: the engineer submits a request through the access management system with a
business justification; access is granted for a time-limited session; the session is logged
with the justification; anomalous activity during the session is classified as a security
incident. It applies to onshore engineers and DBAs and is **never available to offshore
contractors**.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-12 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-13 -->

For a production DBA, write access requires the break-glass procedure and generates a
**timestamped audit event before the elevated session is opened**, visible to the security
team in real time.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-7 -->

## Secrets management {#secrets}

A secret is any value that, if exposed, would allow unauthorized access: passwords, API keys,
tokens, private keys, certificates, connection strings containing passwords, PGP/GPG private
keys. It is **not** public keys, environment identifiers, non-sensitive URLs, or feature flag
keys (which are designed to be readable).
<!-- source: CSN-Secrets Management-140826-132810.md#page-1 -->

**The reference pattern:** application code and configuration contain only a *secret reference*.
The secret provider is the only system that ever holds the plaintext. `ISecretProvider` is the
only interface application code uses, resolving to AWS Secrets Manager in production,
environment variables locally, and injected pipeline secrets in CI/CD.
<!-- source: CSN-Secrets Management-140826-132810.md#page-1 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-4 -->

### Naming convention {#secret-naming}

```
cnp / {environment} / {tenant-or-global} / {category} / {name}
```

```
cnp/prod/global/db/cnp-global-rw            # shared database read/write
cnp/prod/ut/db/cnp-ops-rw                   # Utah cnp_ops read/write
cnp/prod/ut/dc-feed/snap-sftp               # Utah SNAP SFTP credentials
cnp/prod/global/oidc/broker-signing-key     # OIDC signing key
cnp/prod/global/external/launchdarkly-sdk
cnp/staging/ut/db/cnp-ops-rw                # staging paths are separate
```

The point of the hierarchy is that **access policies are writable at the path level**: a state
service gets `cnp/prod/ut/*` and `cnp/prod/global/*` and cannot read `cnp/prod/me/*` because
it has no policy for that path. Per-tenant isolation enforced by the secret store's own access
control, with no application-level filtering — the direct parallel to schema-per-tenant in the
database.
<!-- source: CSN-Secrets Management-140826-132810.md#page-2 -->
<!-- source: CSN-Secrets Management-140826-132810.md#page-4 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-5 -->

### Rotation {#rotation}

| Secret type | Rotation | Who |
|---|---|---|
| Database credentials | 90 days, automated | Platform-managed; the application must tolerate an overlap window where both credentials are valid |
| OIDC client secrets | 180 days | Platform-managed, or immediate on suspected compromise |
| External API keys (LaunchDarkly, Snowflake) | 180 days | Platform-managed with graceful overlap |
| Signing keys | 180 days | Platform-managed, graceful rotation |
| PII field encryption keys | Annual | Requires re-encryption of existing data |
| **DC feed SFTP credentials** | Per state agency agreement | **Not platform-managed** — the state agency initiates |
| Infrastructure credentials | TBD — needs infosec input | CloudOps + Infosec |
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-5 -->
<!-- source: CSN-Secrets Management-140826-132810.md#page-1 -->

**Externally-managed rotation** (DC feeds) is a coordinated five-step process: the state agency
gives at least 24 hours notice → the onshore config team receives the new credential through a
secure out-of-band channel (**not email**) → onshore updates the secret via the DC Feed Adapter
API → the next nightly load picks it up automatically → onshore confirms success and the state
retires the old credential. **No deployment required for any rotation.**
<!-- source: CSN-Secrets Management-140826-132810.md#page-3 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-19 -->

### Hard rules for credential handling {#credential-rules}

- **No credentials in config files.** No SFTP hostname, username, password, PGP private key or
  passphrase in `appsettings.json`, environment variable files, Helm values or source code.
  **This is a PR-blocking finding.**
- No secret value ever appears in application logs, or in an application database.
- **On SFTP auth failure:** invalidate the Secrets Manager cache and retry once with a freshly
  fetched secret. **Never cache a failed credential** for the process lifetime.
- **PGP passphrases are stored as `char[]`, not `string`**, so they can be zeroed after use.
- DC feed temp files (decrypted before parsing) are cleaned up immediately after parsing.
- On suspected compromise: rotate immediately. **Service outage is accepted over continued
  exposure.**
- Every secret has a rotation policy — *"never rotate" is not a valid policy.*
- Secret values are transmitted only via the secret store API — never email, Slack or
  ticketing.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-6 -->
<!-- source: CSN-Secrets Management-140826-132810.md#page-5 -->

### The one rule that inverts under incident {#forensics}

> **On a confirmed incident: do NOT rotate credentials or delete logs until forensics is
> complete. Preserve all state.**

Rotating credentials or purging logs before forensics can destroy evidence needed for breach
notification compliance. This directly overrides the ordinary "rotate immediately" rule, and
the two appear side by side in the source.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-7 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-20 -->
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-5 -->

### Secret audit trail {#secret-audit}

Every create, read, update, rotation, revocation and deletion is logged, in **two tiers**:
read events go to a high-volume append-only log feeding anomaly detection (retained 90 days),
while rotation and revocation events go to a low-volume store that must be **immediately
queryable by the security team** (retained permanently). The log is write-only and cannot be
modified even by the platform operations team.
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-7 -->
<!-- source: CSN-Secrets Management-140826-132810.md#page-4 -->

## Database role separation {#db-roles}

Two roles exist. **No others should ever be created for application or human use.**

| Role | Can | Used by |
|---|---|---|
| `cnp_ops` (app role) | INSERT/UPDATE/DELETE on operational tables; **read-only** on schema-managed tables (`WorkflowStates`, `ConfigDefinitions`, transition conditions/actions); cannot run DDL | Application service only, via a Secrets Manager credential |
| `cnp_migration` | Full DDL on all tables | **CI/CD pipeline only** |
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-2 -->

The app role's read-only grant on the tables the triggers read is deliberate: **the app role
cannot alter them to bypass trigger logic.**
<!-- source: CSN-Workflow Engine-140826-132724.md#page-7 -->

> `cnp_migration` **is not for humans.** It must not appear in any Secrets Manager path
> accessible to engineers. It is provisioned only for the CI/CD pipeline. *"If anyone requests
> this credential directly, that is an access control violation."*
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-2 -->

A third role, `cnp_readonly` (no INSERT/UPDATE/DELETE anywhere), is named in the workflow
engine document for offshore engineers doing debugging and query work in dev/staging.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-7 -->

## Code review requirements by risk category {#code-review}

| Change type | Review requirement |
|---|---|
| New named hook (condition or action) | Onshore review + `IsFederal` classification confirmed + **guardrail assertion test in the same PR** |
| New `ConfigDefinitions` row with `IsFederal = true` | Onshore review + federal citation confirmed against current regulation + guardrail test |
| **Changes to federal math** (CEP, CACFP tier, SFSP rate) | **Two-person review**: one onshore engineer + one domain expert. FNS regulatory reference required in the PR description |
| Changes to audit trail logic | Onshore review. Any reduction in audit coverage requires explicit justification |
| Migrations touching override or reference tables | Onshore review. **Trigger integrity must be verified post-migration** |
| Changes to `ISecretProvider` implementations | Onshore review. No production credential values may appear in the diff |
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-4 -->
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-5 -->

Enforced mechanically via `.github/CODEOWNERS`: any PR touching `/src/Hooks/`,
`/src/Compliance/`, `/src/Audit/` or `/migrations/` automatically adds the onshore tech lead
as a required reviewer. Any PR modifying `ConfigDefinitions` or `WorkflowTransitionConditions`
seed data requires the onshore lead. Offshore engineers cannot self-approve any PR. **The
CODEOWNERS file is itself a protected path.**
<!-- source: CSN-Prototype-140826-133159.md#page-6 -->

## Test data {#test-data}

**No real child nutrition data** — eligibility records, household income, DC matches, NDL
records — in development or staging. This is absolute *"regardless of whether the data appears
'anonymized' through column masking alone."*

Two sanctioned approaches:

1. **Synthetic generation** — realistic but entirely fabricated, preserving statistical
   distributions (free/reduced/paid ratios by program type) without using real records.
2. **Production replay in an isolated environment** — for CTS/DIS replay validation, real data
   may be used in a *dedicated isolated validation environment with onshore-only access*. This
   is explicitly **not** a staging environment for development purposes.
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-4 -->

## Incident response {#incident-response}

Within 1 hour of detection: **contain** (revoke access or isolate the component), **preserve**
(do not delete logs or rotate credentials until forensics is complete), **notify** (LINQ
security lead + VP Engineering within 1 hour; Legal within 4 hours).

| Notification target | Deadline |
|---|---|
| LINQ Security lead + VP Engineering | Within 1 hour of detection |
| Legal | Within 4 hours of detection |
| State agency | Within 24 hours of confirmed breach — *regardless of the state law deadline*, because state law deadlines are a floor, not a target |
| USDA FNS | Consult Legal; may be required if program integrity is affected |
| State law deadline | Varies. AK, HI, ME, MO, UT and WI have minimum 72-hour windows. **The most restrictive state law applies across all 28 states** |
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-15 -->
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-5 -->
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-6 -->

An incident includes *"any system behavior that may have disclosed one state's data to another
state's users."*
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-5 -->

## Open compliance items and their owners {#open-items}

Recorded in the source as pending or not started. Several are hard gates.

| Item | Status | Owner | Required before |
|---|---|---|---|
| State DPA review for all 28 states | Pending | Legal | First state production go-live |
| Offshore contractor data handling agreement template | Pending | Legal + Engineering lead | Before offshore access provisioned |
| Offshore contractor registry | Pending | Engagement manager | **Immediately** |
| Synthetic test data generation pipeline | Not started | Engineering | Before offshore development begins |
| **Break-glass access management system** | **Not started** | DevOps / Security | Before production environment provisioned |
| DR plan finalization and test | Under assessment | DevOps / Engineering lead | First state production go-live |
| **NIST SP 800-171 gap assessment** | **Not started** | Security lead | Before production environment provisioned |
| Offshore DLP controls deployment | Not started | Security / DevOps | Before offshore receives any environment access |
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-6 -->
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-7 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-14 -->

## A candid note left in the source {#dr-note}

The Disaster Recovery section of the Access Governance document opens with an author's
annotation: *"This is completely fabricated. Need to discuss with Ed."* The Infrastructure
document independently flags the same targets as *"proposed, not confirmed"* and instructs
readers not to treat them as commitments until the DevOps/Engineering lead signs off.

The targets, on that basis, are: RPO 1 hour, RTO 4 hours, Aurora PITR with 35-day retention,
daily snapshots retained 1 year, cross-region backup replication (us-east-1 → us-west-2).

**No state can go live until DR posture is confirmed, tested and documented. This is stated as
a hard gate, not a recommendation** — a production system handling federal child nutrition
data with no confirmed DR plan is not compliant with NIST SP 800-171 CP and IR control
families.
<!-- source: CSN-Access Governance & Data Handling Policy-140826-133138.md#page-6 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-15 -->
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-16 -->

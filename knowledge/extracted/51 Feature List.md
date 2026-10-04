<!-- EXTRACTED from knowledge/inbox/51 Feature List.xlsx on 2026-09-09T13:30:37Z -->
<!-- DO NOT EDIT. If extraction is wrong, fix the extractor and re-run. A
     hand-patched extraction no longer matches its source, and once that is
     true of one file no citation in this corpus can be trusted. -->


<!-- sheet: Feature Detail -->

## Sheet: Feature Detail

| Feature Detail — 51 Refined Features (source for Role Summary totals) |  |  |  |  |  |  |  |
|---|---|---|---|---|---|---|---|
| Sprint | Weeks | Ref ID | Capability Area | Refined Feature | Complexity | Effort (hrs) | Skilled Role |
| Mob | Weeks 1-2 | RF-05 | Security & Auth | Close the Keycloak-vs-Cognito decision in Week 0 before build starts- Harmony Auth/Cognito decided by client | S | 16 | Security & Auth |
| Mob | Weeks 1-2 | RF-44 | Data & Architecture | Schema evolution is migration-managed (EF Core); hardcoded year constants and versioned parallel schemas prohibited | M | 32 | Data Engineer |
| Mob | Weeks 1-2 | RF-47 | Data & Architecture | Secrets: single ISecretProvider fronting AWS Secrets Manager; path scheme cnp/{env}/{tenant\|global}/{category}/{name}; no plaintext in config | M | 48 | Data Engineer |
| Mob | Weeks 1-2 | RF-48 | DevOps / Environments | AWS foundation (Week 0-1): Aurora x2, ECS containers, ElastiCache Redis, Secrets Manager, GitHub CI/CD - nothing else starts before this | L | 72 | DevOps / Platform |
| Mob | Weeks 1-2 | RF-49 | DevOps / Environments | Environment posture: dev + staging on shared Aurora; demo + UAT on dedicated clusters; all deploys tag-based; us-east-1 only | M | 40 | DevOps / Platform |
| Mob | Weeks 1-2 | RF-50 | DevOps / Environments | Synthetic data only in every environment offshore can touch; the synthetic-data pipeline must exist before offshore work begins (Week 0 gate) | L | 56 | DevOps / Platform |
| Mob | Weeks 1-2 | RF-51 | DevOps / Environments | Configuration specialist signs off the demo environment before the October demonstration | S | 16 | DevOps / Platform |
| S1 | Weeks 3-4 | RF-01 | Security & Auth | Real OIDC login against the demo-state Keycloak realm; no mock tokens anywhere in the flow | L | 60 | Security & Auth |
| S1 | Weeks 3-4 | RF-02 | Security & Auth | Subdomain-driven tenant resolution: subdomain -> YARP -> Keycloak realm -> ICnpContext selecting cnp_global + the state cnp_ops connection | L | 48 | Security & Auth |
| S1 | Weeks 3-4 | RF-03 | Security & Auth | JWTs carry roles + tenant scopes only (never raw permissions), held in service memory, never localStorage | S | 20 | Security & Auth |
| S1 | Weeks 3-4 | RF-04 | Security & Auth | SSO via Keycloak as OIDC broker, extensible to all states; Phase 1 wires one demo-state realm | M | 32 | Security & Auth |
| S1 | Weeks 3-4 | RF-41 | Data & Architecture | Two Aurora PostgreSQL databases: cnp_global (shared) + one cnp_ops (demo state); the database boundary is the tenant boundary | L | 64 | Data Engineer |
| S1 | Weeks 3-4 | RF-45 | Data & Architecture | Backend: .NET 8 + MediatR pipeline, net-new build (no copy-paste from legacy CTS/DIS), built to the published interface contracts | L | 64 | Data Engineer |
| S2 | Weeks 5-6 | RF-20 | Workflow Engine | Every workflow row carries an IsFederal flag; federal states/transitions/conditions/actions are guardrailed at INSERT | M | 40 | UI + Backend |
| S2 | Weeks 5-6 | RF-21 | Workflow Engine | Tenant-specific customisation expressed only via TenantTransitionOverrides in cnp_ops - never state-keyed branches in code | M | 32 | UI + Backend |
| S2 | Weeks 5-6 | RF-30 | Configuration Engine | Configuration resolves through 3 layers - Platform Default -> Program Override -> Tenant Override, most-specific-wins | L | 64 | UI + Backend |
| S2 | Weeks 5-6 | RF-31 | Configuration Engine | Every key is typed, bounded (Min/Max) and effective-dated; every override needs Effective Date + Justification | L | 56 | UI + Backend |
| S2 | Weeks 5-6 | RF-32 | Configuration Engine | IsFederal = true blocks tenant overrides at write time; no endpoint may override a federal-locked value | M | 28 | UI + Backend |
| S2 | Weeks 5-6 | RF-33 | Configuration Engine | ICnpConfigService.GetValue<T>() is the sole accessor; direct config-table reads prohibited | M | 36 | UI + Backend |
| S2 | Weeks 5-6 | RF-36 | Configuration Engine | ~5 module-level LaunchDarkly feature flags wired end-to-end (incl. frontend route guards) | M | 32 | UI + Backend |
| S2 | Weeks 5-6 | RF-06 | Security & Auth | Role-based authorisation with 3 override layers; explicit Revoke beats any lower Grant | L | 72 | Security & Auth |
| S2 | Weeks 5-6 | RF-07 | Security & Auth | All authorisation decisions flow through ICnpPermissionService; direct role checks prohibited | M | 40 | Security & Auth |
| S2 | Weeks 5-6 | RF-18 | Workflow Engine | Thin, data-driven workflow executor - all states, transitions, guards and side-effects live as rows in 5 cnp_global tables | XL | 100 | UI + Backend |
| S2 | Weeks 5-6 | RF-19 | Workflow Engine | Conditions and actions resolve to named hooks registered per entity type and resolved by DI; engine never calls business code directly | L | 56 | UI + Backend |
| S2 | Weeks 5-6 | RF-22 | Workflow Engine | Every executed transition writes audit-trail rows (who, when, from/to state, outcome of conditions and actions) | M | 28 | UI + Backend |
| S3 | Weeks 7-8 | RF-08 | Security & Auth | IsFederal permissions are irrevocable by any override layer | M | 24 | Security & Auth |
| S3 | Weeks 7-8 | RF-09 | Security & Auth | UserRoleAssignments carry ScopeType, enforced automatically at the repository layer (replaces ~5,082 legacy per-object ACL rows) | L | 64 | Security & Auth |
| S3 | Weeks 7-8 | RF-10 | Security & Auth | Deliver the SECURITY permission domain + demo roles (SponsorDirector/Staff, Caseworker/Reviewer, StateAgencyAdmin, LINQConfigAdmin) | M | 32 | Security & Auth |
| S3 | Weeks 7-8 | RF-23 | Federal Controls | NoNDLMatch federal pre-condition hook on the ApproveApplication transition, checking org name, EIN and named principals against NDL | L | 48 | UI + Backend |
| S3 | Weeks 7-8 | RF-24 | Federal Controls | ConfirmedMatch is an absolute, non-overridable block on approval - no user, admin or config can bypass | M | 24 | UI + Backend |
| S3 | Weeks 7-8 | RF-25 | Federal Controls | PossibleMatch routes to NdlOverrideRequests for human review rather than blocking outright | M | 32 | UI + Backend |
| S3 | Weeks 7-8 | RF-26 | Federal Controls | NDL source may be a stub/synthetic dataset, but blocking behaviour and audit records are real | M | 28 | UI + Backend |
| S3 | Weeks 7-8 | RF-27 | Federal Controls | On approval, FreezeClaimLaws writes an immutable ClaimLaws record snapshotting the eligibility rules in force | L | 56 | UI + Backend |
| S4 | Weeks 9-10 | RF-11 | Applications | Sponsor can view a sponsor-scoped application list, open detail, complete the SNP annual application and submit it | L | 64 | UI + Backend |
| S4 | Weeks 9-10 | RF-12 | Applications | Application detail renders workflow action buttons dynamically - only transitions valid for state, role and permissions shown | M | 40 | UI + Backend |
| S4 | Weeks 9-10 | RF-13 | Applications | Caseworker can review a submitted application and either advance it or return it with corrections required | M | 40 | UI + Backend |
| S4 | Weeks 9-10 | RF-14 | Applications | State user with approval permission can approve; approval fires federal pre-condition checks and configured side-effects | M | 36 | UI + Backend |
| S4 | Weeks 9-10 | RF-15 | Applications | SNP lifecycle seeded as workflow config: Draft -> Submitted -> Under Review -> (Returned) -> Approved, Denied terminal | M | 32 | UI + Backend |
| S4 | Weeks 9-10 | RF-16 | Applications | Submission validation failures recorded and visible to the sponsor, with state-side override where config permits | M | 32 | UI + Backend |
| S4 | Weeks 9-10 | RF-17 | Applications | Server-defined application form (FormDefinition metadata -> server-built field config); client never hardcodes structure | L | 56 | UI + Backend |
| S5 | Weeks 11-12 | RF-28 | Federal Controls | The ClaimLaws freeze is visible in the UI after approval (demo shows the frozen snapshot) | M | 24 | UI + Backend |
| S5 | Weeks 11-12 | RF-29 | Federal Controls | One generic freeze mechanism serves all programs via configuration - eliminates legacy per-program duplicated procedures | M | 32 | UI + Backend |
| S5 | Weeks 11-12 | RF-34 | Configuration Engine | Config Admin screen lets an authorised user change a tenant-level setting, observably live in under 10 minutes | L | 60 | UI + Backend |
| S5 | Weeks 11-12 | RF-35 | Configuration Engine | Every configuration write is logged to FieldChangeLog | S | 24 | UI + Backend |
| S5 | Weeks 11-12 | RF-37 | Audit | Append-only audit layer with 100% capture of the demo flow | L | 56 | Audit + Config Admin |
| S5 | Weeks 11-12 | RF-38 | Audit | Audit records capture actor, timestamp, entity, action and before/after content (entity snapshots as JSONB) | L | 56 | Audit + Config Admin |
| S5 | Weeks 11-12 | RF-39 | Audit | One audit timeline screen presents an application history end to end, human-readably, for the demo | M | 48 | Audit + Config Admin |
| S5 | Weeks 11-12 | RF-40 | Audit | Audit data is immutable - no update or delete paths | S | 20 | Audit + Config Admin |
| H | Weeks 13-14 | RF-42 | Data & Architecture | Build only what the flow needs: ~20-30 cnp_global and ~60-80 cnp_ops tables; other domains ship as empty migration stubs | L | 72 | Data Engineer |
| H | Weeks 13-14 | RF-43 | Data & Architecture | Data spine ProgramGroups -> ProgramGroupYears -> ProgramGroupEnrollments; entities FK-chain through ProgramGroupYears | L | 48 | Data Engineer |
| H | Weeks 13-14 | RF-46 | Data & Architecture | Frontend: Angular 17+ SPA, net-new repo, reusing @linq/snackpaq + Angular Formly; program-year-scoped URLs | L | 64 | Data Engineer |
|  |  |  |  |  | TOTAL | 2264 |  |

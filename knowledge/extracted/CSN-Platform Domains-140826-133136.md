<!-- EXTRACTED from knowledge/inbox/CSN-Platform Domains-140826-133136.pdf on 2026-09-09T13:30:49Z -->
<!-- DO NOT EDIT. If extraction is wrong, fix the extractor and re-run. A
     hand-patched extraction no longer matches its source, and once that is
     true of one file no citation in this corpus can be trusted. -->


<!-- page: 1 -->
Platform Domains
The domains outlined below are the result of integrating the  with
 and new requirements. This incorporates relevant patterns and
structures to strengthen the overall model.
Overview
AUTHORITY BOUNDARY — nothing below decides money, eligibility, or enforcement
SPECIALIST BOUNDARY — business-critical, not authoritative
OBSERVATIONAL BOUNDARY — downstream consumes facts; never influences decisions
above
cnp_global (1 shared Aurora instance — 387 tables: rates, types, codes, templates)  +  cnp_ops
(1 Aurora per state — 1,015 operational tables). Database IS the tenant boundary. Annual rates =
INSERT with EffectiveDate. Zero SP changes.
initial design
Domains_Combined_v3
1 · Authoritative   — hold legal, financial & enforcement authority
Claims & Reimbursement  ·  Accounting & Disbursement  ·  Compliance & Review  ·  Eligibility & Direct
Certification
2 · Foundational   — constrain inputs; never decide outcomes
Identity & Access  ·  Configuration & Tenant  ·  Sponsor & Site Registry  ·  Applications & Agreements  · 
Program Registry (DATA SPINE)
3 · Operational   — own program rules & integration surfaces
Programs: SNP  ·  CACFP  ·  DCH  ·  SFSP  ·  FFVP  ·  SSFO  ·  CEP     Platform services: Forms Engine  · 
Workflow & Task Mgmt  ·  Integration & Data Exchange  ·   Document Library
4 · Observational   — read models & outbound services only
Reporting & Analytics (→ Snowflake)  ·  Audit & Observability  ·  Notifications  ·  Communications ·  Reference
Data & Transparency  ·  LaunchDarkly
<!-- page: 2 -->
Tier 1 · First-Class Authoritative Domains: Legal, financial & enforcement
authority
Tier 2 · Foundational: Constrain inputs to authoritative domains; never decide
outcomes
who, what, where before any program work happens
Claims & Reimbursement
Facts of service. Federal math. Never money.
Mal counts. Claim validation (federal SPs →
C# with characterization tests). Effective-
dated ClaimLaws. Advance requests. Claim
locking. Non-congregate 3-mode validation.
Section 4/11 split for FNS-10. Auto-Decline
Claims (ME pattern — configurable per
tenant via feature flag).
Accounting & Disbursement
Federal grants. State money flowing down.
Grant tracking. DOF calculation. FNS reports
(10/44/418/640/905). Repayment schedules.
IAccounting Exporter per state. CN
Financials. Earnings/269. AFR Sponsor
Reporting (Annual Financial Report — IN
center/DCH variants; ME NSLP variant —
both are reference implementations).
Compliance & Administrative Review
Enforcement. Consequences.
Risk scoring. 3-year review cycle. Fiscal
workbook FA1–FA4 (moved here from
Accounting — these are enforcement
consequences, not financial instruments).
Serious Deficiency. School Reviews.
Technical Assistance.
Eligibility & Direct Certification
Who is eligible. Legal determination.
DC matching (SNAP/Medicaid/TANF/FDPIR).
DirectVer (Indiana) — sponsor-facing
student search and application list upload;
Indiana's 5-class model is the deepest DC
implementation in the LINQ portfolio and is
the reference design for this domain. FRPL.
Verification. ISP pipeline → CEP.
Core2_DirectCertification* (98) + legacy dbo
(49).
<!-- page: 3 -->
Tier 3 · Operational: Own program rules & integration surfaces
PROGRAM DOMAINS:OWN PROGRAM RULES & CLAIM LAWS
Identity & Access Management
Auth, roles, SSO, OIDC
CnpObjects rights model. Multi-tenant
ICnpContext (resolves GlobalDb + StateDb
connections). Harmony auth OIDC.
ApiAuthenticationTokens. Password policy.
JumpSessions (impersonation audit).
Configuration & Tenant Management
State variation lives here — never in code branches
Feature flags (LaunchDarkly). CnpDefaults.
Program year rules. ClaimRateAmounts
(effective-dated — annual rate updates are
INSERTs here, not deployments). Tenant
provisioning.
Site & Sponsor Management
Authoritative record of who participates
Sponsors, SFAs, sites, providers, addresses.
NDL verification. Agreement number
generation. Associates (FSMC-linked).
Program enrollment linkage to Program
Registry.
Applications & Agreements
Enrollment & eligibility to participate. 
Application packets. Sponsor/site/provider
applications. Annual Forms framework
(AnnualFormTypes, AnnualFormSessions).
Annual rollover engine. Board members.
Pre-screen. Potential sponsor pipeline.
SNP  School Nutrition
NSLP / SBP rules. SSO /
SSFO (non-congregate
PY2024+). SMP. PLE. Meal
pattern compliance. Food
safety. Professional
standards. October survey.
Provision 2/3 ratios.
CACFP  Child & Adult
Care
Center program rules. VCA
Checklist (16-table scoring
module). Institution
management plans. ACQR
reporting. Center budgets.
DCH review track.
DCH  Day Care Home
First-class program domain
— not embedded in
CACFP. Provider
applications. Provider
claims. DCH sponsoring
org. Tier I/II rates. 23-day
max operating days.
License expiry gate.
<!-- page: 4 -->
MODULES:BUSINESS-CRITICAL OPERATIONAL MODULES
SFSP  Summer Food
Summer site rules. Non-
congregate service — 3
modes: congregate / non-
cong / mixed. Rural & heat
waiver (Healthy Meals
Healthy Kids Act 2022).
2% second-meal rule
(sponsor-level calculation).
FFVP  Fresh Fruit &
Veg
Grant-based (not
reimbursement-based).
Site invitations. Grant
allocations. Monthly
purchase claims. FFVP
Application workflow
(Maine reference impl) —
dedicated application
packet separate from
eligibility and entry. First-
class domain — not
embedded in SNP.    
CEP  Community
Eligibility
ISP × 1.6 = claiming %
(capped 100%). CEP
groups + sites. 4-year
cycle. Dedicated REST API
bounded context — not
embedded in SNP. DIS
CnpCepApi already proved
this boundary.
SSFO Seamless
Summer
Distinct ClaimLaws and site
application rules from
NSLP. Non-congregate
applies here (PY2024+).
~16 dedicated tables.
Architect's call — correct
separation.Distinct
ClaimLaws and site
application rules from
NSLP. Non-congregate
applies here (PY2024+).
~16 dedicated tables.
Architect's call — correct
separation.
<!-- page: 5 -->
PLATFORM SERVICES: SHARED INTEGRATION SURFACES
VCA Checklist
16 tables.
Viability/Capability/Accoun
tability self-assessment.
VCAScoringTools
definitions in cnp_global
(shared all states). Sponsor
instances in cnp_ops.
Budget Module
Budgets, Budget Details,
Budget Items, Budget
Labor Details, Budget Meal
Worksheets. Ohio extends
to 42 tables in cnp_ext.
Contracts &
Procurement
FSMC contracts. Written
Approval Requests. Capital
Expenditure Requests.
Federal Award Letters.
Procurement review track.
Architect's call — correct
separation from
Applications.
Risk Management
Risk scoring. Review
prioritization dashboard.
Reports. Feeds
Compliance review
scheduling — does not
decide enforcement
outcomes. Stays specialist.
Training & Tech Assist
Professional Standards
(USDA-mandated). Course
catalog in cnp_global. TA
codes, areas, items,
focuses. HI is only DIS
state with this built.    
Food Distribution
128–304 tables embedded
in shared dbo — cannot be
cleanly separated without
schema surgery. Ohio/WY
have fdp/gratefdp
schemas. Decision
required before Phase 3.
Waivers & Approvals
Waiver Items, Waiver
Types. Written Approval
Requests (USDA
exceptions). Capital
Expenditure Requests.
Linked to applications and
claims.
<!-- page: 6 -->
PER=STATE ADAPTER PATTERN
Addresses failure mode #7 — "state-specific behavior had no clean home." Every state-specific
behavior lives in one of these four adapter slots. No state-keyed if/else branches anywhere in
shared platform code.
Forms Engine
Year-versioned definitions in cnp_global.
Metadata-driven rendering.
AnnualFormTypes, ReviewVersions,
ReviewQuestions. Replaces forked
versioned ASPX pages.
Integration & Data Exchange
IDcFeedAdapter · IAccountingExporter ·
ILicenseAdapter · IEdFiAdapter. USDA
ArcGIS. NDL. LaunchDarkly Session Replay.
Format translation only.
Workflow & Task Management
Hangfire background jobs. FFY rollover
automation. CnpTasks. Review scheduling
calendar. CTM replacement
Communications & Notifications
Email templates (cnp_global).
MessageBoards. BroadcastEmail. Intercom
in-app messaging. System alerts. Outbound
only — no business rules. 
Document Library
File storage. Form PDF snapshots → S3.
Document versioning. DownloadFormBlobs.
Pre-signed URL generation for historical
form access.
IAccountingExport
er
UT→USAS ·
CO→COFRS ·
SC→CALSTARS ·
MT→SABHRS ·
TN→ISAS ·
OH→SCEIS
IDcFeedAdapter
Per-tenant DC
source config:
SNAP, Medicaid,
TANF, FDPIR.
PGP/SFTP or REST
per state.
IEdFiAdapter
States with Ed-Fi
ODS:
RestEdFiAdapter.
States without:
FlatFileEdFiAdapter
fallback.
ILicenseAdapter
UT→DOPL license
sync. Per-state
childcare provider
license verification.
<!-- page: 7 -->
Tier 4 · Observational: Read models & outbound services; never influence
decisions above
Database Architecture
DATA SPINE
ProgramGroups  →  ProgramGroupYears  →  ProgramGroupEnrollments
Every Application and Claim FK-chains through ProgramGroupYears. It's the structural spine of
the data model.  ·  Definitions in cnp_global · Enrollment records in cnp_ops.
Reporting & Analytics (snowflake)
Read models only
ALL reporting queries run against Snowflake
REPORTING layer — never against Aurora
cnp_ops. FNS-10/44/418/640/905 pre-
materialized nightly. Zero operational DB
contention. Tenant isolation via Snowflake
row access policies. Replaces Architect's
Reporting & Data Export domain as an
application concern.
Audit & Observability
Event consumption only
Never influences behavior. Audit trail for
eligibility, claims, payments, config. Activity
logs. Datadog APM. User access reports.
Notifications & Communications
Outbound only
No business rules. Email templates.
Broadcast messages. Notices. In-app
messaging (Intercom). Discussion board.
System alerts.
Reference Data & Transparency
Lookups — no decisions
Program codes, county types, poverty data,
USDA calendar, FY tables. Public AR
summary portal (feature-flagged per tenant).
CNP_GLOBAL 1 shared instance
Contents: ~387 tables: ProgramMealRates,
ClaimRateAmounts (effective-dated), all
*Types/*Codes/*Statuses, ReviewVersions,
CNP_OPS 1 instance per state
Contents: ~1,015 tables: all Sponsors, Sites,
Applications, Claims, Reviews,
<!-- page: 8 -->
State Variation Handling
ReviewQuestions, VCAScoringTools,
AnnualFormTypes, BudgetItems,
TrainingCourses
Update model: Annual rates = INSERT with
EffectiveDate. Zero deployment. Zero SP
change. Zero per-state work.
Access: Read-only for all state instances.
ICnpReferenceCache (24hr TTL for types,
1hr for rates).
Disbursements, Users, DC records, VCA
instances, Budget instances
Isolation: Database IS the tenant boundary.
No TenantId column needed in operational
tables. State data sovereignty guaranteed at
infrastructure level.
Extensions: cnp_ext schema for state-
specific tables (Ohio Budget+42, GA legacy
tables). Never in shared platform code.
No domain anywhere contains a branch on which state it's running. Every state
difference is a flag, an adapter, a config value, or a separate extension schema.
01  Feature Flags
Launch Darkly
Whole capabilities toggle per tenant — AR
transparency portal, non-congregate SFSP,
state-specific report packs. One codebase,
many footprints.
02  Plug-in Adapters
4 interfaces only
IAccountingExporter (UT→USAS ·
CO→COFRS · SC→CALSTARS ·
MT→SABHRS · TN→ISAS · OH→SCEIS).
IDcFeedAdapter
(SNAP/Medicaid/TANF/FDPIR per tenant).
IEdFiAdapter. ILicenseAdapter.
Cnp.Extensions.<State>.dll resolved at
startup.
03  Configuration
JSON B | cnp_global
State-specific values — claim rate overrides,
deadlines, program-year rules, CnpDefaults
— stored as effective-dated rows in
cnp_global config schema. No schema
04  Extension Schema
cnp_ext per state
Genuinely unique state needs live in cnp_ext
schema within the same Aurora cluster.
Ohio's 42-table budget extension, Georgia's
<!-- page: 9 -->
Appendix
DOMAIN ORIGINS
Added references to DIS items we should include in future State CNP Platform
forking. Readable at runtime, no
deployment.
legacy tables, Iowa's fnm schema. Never
bleeds into shared platform code.
Program Registry (~7 tables) Combined_v3 "Program Registry" is sharper
than "Program Enrollment
Model"
SSFO as own program domain
(~16 tables)
Combined_v3 Distinct ClaimLaws and site
application rules from NSLP
CEP as dedicated bounded
context
New DIS CnpCepApi proved the
boundary works; ISP math
needs isolation
Contracts & Procurement (~57
tables)
Combined_v3 Distinct enough from
Applications; FSMC
procurement is a real
workstream
Training & Technical
Assistance combined (~57
tables)
Combined_v3 Same stakeholders, same
lifecycle — grouping is correct
Fiscal Actions → Compliance,
not Accounting
New FA1–FA4 are enforcement
consequences, not financial
instruments
Reporting → Snowflake
(observational, not operational)
New Reflects database-per-tenant
and Snowflake decisions
Authority tiers New Determines service
dependency rules
Domain / Decision Source Rationale
<!-- page: 10 -->
ClaimLaws mechanism callout New Directly addresses failure
mode #5 (no SP
characterization)
cnp_global / cnp_ops database
split
New Reflects database-per-tenant
decision
VCA Checklist, Budget,
Waivers
Schema analysis Confirmed in all 5 CTS state
schemas
Commodities scope gate Both 128–304 tables embedded in
shared dbo — cannot be
cleanly separated
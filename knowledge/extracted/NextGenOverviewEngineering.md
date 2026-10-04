<!-- EXTRACTED from knowledge/inbox/NextGenOverviewEngineering.pptx on 2026-09-09T13:30:54Z -->
<!-- DO NOT EDIT. If extraction is wrong, fix the extractor and re-run. A
     hand-patched extraction no longer matches its source, and once that is
     true of one file no citation in this corpus can be trusted. -->


<!-- slide: 1 -->

## Slide 1

- A fresh futurefor Child Nutrition Programs
- Features, Workflows, and Professional Services Configurations

> **Speaker notes:** Welcome and set context. This deck has two parts: the customer-facing story about what we're building and why it matters — this is what a state agency would see. Then we'll transition into the technical architecture for the engineering team. Use the first 12 slides to make sure everyone has the same mental model of the product before we get into how it's built.


<!-- slide: 2 -->

## Slide 2

- A look at what we're building...
- A new platform replacing CTS and DIS, managing Child Nutrition Programs across multiple states that will manage every step of the program cycle, including:
- sponsor applications
- site approvals
- monthly claims
- administrative reviews
- corrective actions, and appeals
- Built from the ground up as a single platform that adapts to each state's rules without custom development.
| © EMS LINQ, LLC. All rights reserved. |

> **Speaker notes:** Single platform, full program lifecycle. The key message: this isn't a point solution — it manages everything from sponsor applications through claim payment in one system. Replacing CTS and DIS across multiple states. Worth noting that most state CNP systems today are a collection of disconnected tools — this is a greenfield platform built to handle everything in one place.


<!-- slide: 3 -->

## Slide 3

- 01
- Configuration
- States choose how their program works,within boundaries they cannot cross. Three tiers: self-service in the portal, LINQ-guided setup, or a platform build for code-level changes.
- Configuration is a first-class architectural concern.
- 02
- Federal Protections
- IsFederal is not a setting. It is an architectural constraint enforced at three independent layers: UI, API, and database trigger. No role, script, or direct database write can override it.
- Federal math and requirements are not configurable.
- 03
- Isolation
- At the database level, each state operates in its own PostgreSQL schema
- At the API level, every request carries a JWT issued by Harmony Auth that contains the state tenant scope. The application validates that scope before executing any query
- At the document storage level, S3 keys include the state code in the path, and presigned URLs are generated at read time
- No cross-state reads. No shared mutable state.
- 04
- Immutability
- Nothing disappears quietly. EntitySnapshots capture full record state. FieldChangeLog records every delta. S3 Object Lock (WORM) enforces retention. Auditors get complete chains.
- Audit records are append-only.
- Four Guiding Principles

> **Speaker notes:** 1. This is an expectation from our clients
2. The IsFederal flag is the clearest expression of this: it is enforced at three independent points. The UI suppresses the control entirely for users without the flag. The API validates the flag on every write before the record is persisted. A database trigger rejects any direct write that attempts to set IsFederal = true without meeting the structural preconditions — meaning even a DBA with direct database access cannot override it without triggering a constraint violation. 
3. cross-state data access requires simultaneously defeating the JWT validation layer, the application query layer, and the database schema boundary
4. . FERPA and USDA audit requirements make this non-negotiable, and it's a meaningful architectural decision (append-only audit is a constraint that shapes everything above it).


<!-- slide: 4 -->

## Slide 4

- Domains
- 1 · AUTHORITATIVE
- hold legal, financial & enforcement authority
- Claims & Reimbursement  ·  Accounting & Disbursement  ·  Compliance & Administrative Review  ·  Eligibility & Direct Certification
- ── AUTHORITY BOUNDARY — nothing below decides money, eligibility, or enforcement ──
- 2 · FOUNDATIONAL
- constrain inputs; never decide outcomes
- Identity & Access  ·  Configuration & Tenant  ·  Site & Sponsor Management  ·  Applications & Agreements  ·  Program Registry
- ── SPECIALIST BOUNDARY — business-critical, not authoritative ──
- 3 · OPERATIONAL
- own program rules & integration surfaces
- PROGRAM DOMAINS
- SNP  ·  CACFP  ·  DCH  ·  SFSP  ·  FFVP  ·  SSFO  ·  CEP
- MODULES
- VCA Checklist  ·  Budget  ·  Contracts  ·  Risk Management  ·  Training & Tech Assist  ·  Waivers  ·  Food Distribution ⚠
- PLATFORM SERVICES
- Forms Engine  ·  Workflow & Task Mgmt  ·  Integration & Data Exchange  ·  Document Library
- ── OBSERVATIONAL BOUNDARY — downstream consumes facts; never influences decisions above ──
- 4 · OBSERVATIONAL
- read models & outbound services only
- Reporting & Analytics → Snowflake  ·  Audit & Observability  ·  Notifications & Communications  ·  Reference Data & Transparency

> **Speaker notes:** 31 domains. 4 tiers

Authoritative: they are the only domains that decide whether a claim is paid, whether a sponsor is compliant, or whether a household qualifies. 

Foundational: These domains constrain inputs and establish the structures that authoritative decisions operate on, but they never produce outcomes themselves; they are business-critical without being authoritative.

Operational: These domains generate the facts and transactions that flow upward to be adjudicated, but they do not adjudicate.

Observational: It reads facts produced by the layers above and surfaces them outward, but it never writes back into a decision process.


<!-- slide: 5 -->

## Slide 5

- Multiple Domains, one container
- Wrong boundaries cost more in microservices
- In a monolith, a wrong boundary involves renaming a namespace and moving classes.
- In microservices, it means a new API contract, a data migration, and distributed transaction complexity.
- We can extract services when the evidence says to
- Every domain is already isolated by namespace and database schema. When usage patterns show us a domain needs independent scaling or deployment, we can pull it out.
- Boundaries are a hypothesis
- We drew the domain lines carefully, but the boundaries may not survive contact with real usage. A monolith lets us adjust those lines based on what we learn before we've locked them into service contracts.
- Every domain in this platform is already isolated. They each have their own database tables, don’t reach into another domain's data directly, and communicate through defined interfaces.

> **Speaker notes:** Modular Monolith


<!-- slide: 6 -->

## Slide 6

- Architecture Overview
- Phase 2

> **Speaker notes:** Transition point. Everything before this was the customer story. This and everything after is the technical architecture. Walk the layers top to bottom: Frontend → Identity → Core Engines → Domain Services → Audit → Data → Integrations. The AI panel on the right is Phase 2 — designed but not yet built. Single ECS Fargate container, ASP.NET Core 8 modular monolith, Angular frontend, Aurora PostgreSQL.


<!-- slide: 7 -->

## Slide 7

- Identity & Security
- Identity & Security
- Harmony Auth  ·  LINQ-wide authentication
- OIDC / OAuth 2.0  ·  JWT tokens carry roles + state scope  ·  Multi-Factor Authentication enforced

> **Speaker notes:** Harmony Auth is LINQ's centralized authentication service built on Okta and AWS Cognito. All LINQ apps authenticate through it. OIDC/OAuth 2.0 flow: user hits the app, redirects to IdP for login, Harmony Auth returns ID and access tokens, app validates them via Harmony Auth. JWT carries both the user's roles AND their state scope — a Virginia user literally cannot make a request that touches Alabama data. MFA enforced for all users with no admin override.


<!-- slide: 8 -->

## Slide 8

- Core Engines
- Workflow Engine
- Governs every approval process on the platform.
- Reads a table, evaluates conditions, checks permissions, and fires actions.
- ✓  What Clients can configure:
- Add approval steps, assign roles to states, configure routing rules, and set notification triggers.
- ✕  What requires development:
- Federal approval requirements cannot be removed.
- States with claiming consequences require development.
- Form Engine
- Renders and processes the forms that sponsors and caseworkers fill out.
- Forms have conditional logic that’s evaluated at runtime based on program, scenario, and user role.
- ✓  What Clients can configure:
- Field visibility, required/optional rules, and validation for fields the code doesn't branch on.
- ✕  What requires development:
- Fields that drive form behavior (e.g. site type) are set at implementation.
- Review Instrument Engine
- Data-driven review instruments: questions, scoring, and applicability rules
- ✓  What Clients can configure:
- Add questions, edit text, configure scoring criteria, and define which instruments apply to which reviews.
- ✕  What requires development:
- Review workflow structure (on-site vs. desk, findings flow) is set at implementation.
- Every page and function is a securable object with individually assignable view, add, modify, delete, and admin rights.
- Starts with 9 base roles; fully customizable from there.
- ✓  What Clients can configure:
- Create roles, assign rights to roles, and assign users — fully self-service. can create
- ✕  What requires development:
- New platform objects (new pages, new functions) can only be added through a code deployment.
- Rights Model
- Anything flagged as isFederal can ONLY be changed via code

> **Speaker notes:** The four engines are program-agnostic — they don't know if they're running an SNP claim or a CACFP review. What makes them behave correctly for each program is configuration, not code.

Workflow Engine: any process with approval steps runs through this — claim submission and site application are both driven by the same engine, with different configurations.

Form Engine: any data collection uses this. A form in SNP and a form in CACFP are both built and rendered by the same engine. When a federal form changes, the configuration updates, not the code.

Review Instrument Engine: the structured checklist tool for compliance monitoring. Different programs have different instruments; the same engine renders, scores, and records findings for all of them.

Rights Model: every page and function is a securable object with view, add, modify, delete, and admin rights. Starts with 9 base roles — fully customizable from there. Anything flagged isFederal can only be changed via code, enforced at the database level.


<!-- slide: 9 -->

## Slide 9

- Configuration Boundaries
- Client Self-Service
- Clients can do this today, without calling us
- ·  Workflow routing and approval steps
- ·  Form field visibility and required rules
- ·  Notification content and thresholds
- ·  Review instrument questions and scoring
- ·  User roles and permission assignments
- ·  Document requirements and expiration rules
- LINQ Implementation Team
- Configured at onboarding and on request
- ·  System-wide settings (CnpDefaults)
- ·  Federal report field mappings
- ·  Program year activation
- ·  Feature flag configuration
- ·  Schema provisioning for new states
- ·  Integration endpoint configuration
- Development Required
- This requires a code change and a release
- ·  New transaction types
- ·  Site/sponsor types that change form behavior
- ·  New validation error logic
- ·  New field types in the Form Engine
- ·  Claiming calculation rules
- ·  New program types

> **Speaker notes:** Three tiers engineers need to understand when building or modifying features. Client self-service lives in the Config Admin UI and takes effect immediately — workflow routing, form rules, roles, notifications, document requirements, review instrument questions. LINQ Implementation Team tier covers things set at onboarding or changed on a service request — CnpDefaults, federal report mappings, schema provisioning for new states, feature flags. Development Required is anything where the code has to branch differently based on the value — new transaction types, new field types, claiming calculation changes, new program types. The rule: if the code cares about the value, it's a dev ticket.


<!-- slide: 10 -->

## Slide 10

- Domain Services
- Applications & Agreements
- ·  Sponsor and site applications
- ·  Annual renewals and amendments
- ·  Pre-screening and eligibility packets
- ·  Multi-year version history
- ·  Bulk approvals and returns
- Claims & Reimbursement
- ·  Monthly claims entry FA1–FA4
- ·  Claim validation and error feedback
- ·  Automated reimbursement calculation
- ·  Claim freeze and lock controls
- ·  Federal report generation (FNS-10/418/44)
- Eligibility & Direct Certification
- ·  Direct Certification via VDSS feed
- ·  Household applications
- ·  Verification processing
- ·  CEP administration
- ·  Multi-year eligibility history
- Compliance & Review
- ·  Administrative reviews
- ·  Procurement reviews
- ·  Configurable review instruments
- ·  Findings, CADs, recommendations
- ·  Correspondence tracking
- Accounting & Finance
- ·  Payment processing
- ·  Offset and recovery tracking
- ·  Oracle Financials export adapter
- ·  Grant drawdown reporting
- ·  Prior-year fiscal actions
- Programs
- ·  NSLP · SBP · CACFP
- ·  SFSP · SMP · CEP
- ·  Cross-program participation
- ·  Program-specific rules enforced
- ·  IsFederal guardrail per program

> **Speaker notes:** Six domain groupings covering the full program lifecycle. These are business capability boundaries, not microservices — everything runs in one container but each domain has its own namespace and its own database tables. Claims & Reimbursement covers FA1-FA4 claims entry, edit checks, freeze-on-approval, and FNS federal report generation. Compliance & Review covers both administrative and procurement review workflows — both use the Review Instrument Engine. Eligibility & DC handles the VDSS feed and household applications. Accounting covers Oracle Financials integration and payment tracking.


<!-- slide: 11 -->

## Slide 11

- Audit
- Every write operation on the platform (save, submit, approve, reject, and override) is captured automatically.
- What Gets Captured
- Full state snapshot at each event
- Every field that changed, before and after
- Who made the change (user + role)
- When it happened (timestamp)
- What workflow state the record was in
- What You Can Do With It
- Reconstruct the full history of any record
- Answer "who approved this and when?"
- Produce audit trails for federal reviewers
- Support compliance investigations
- Query point-in-time state for any entity
- How It's Protected
- Append-only. Records cannot be modified
- S3 Object Lock (WORM) for long-term retention
- No admin or script can delete audit records
- Retained per compliance retention policy
- Tamper-evident by design

<!-- slide: 12 -->

## Slide 12

- Integrations
- DC Feeds
- Direct Certification
- ·  Automated SFTP retrieval from VDSS
- ·  SNAP, Medicaid, and TANF eligibility files
- ·  Nightly processing with error handling
- ·  PGP-encrypted in transit
- ·  Results stored per state schema
- State Financial
- Systems
- Oracle Financials / VASNP
- ·  Nightly accounting export adapter
- ·  Grant drawdown and payment data
- ·  Reconciliation-ready format
- ·  Config data only. No code in payload
- ·  State-specific account code mapping
- Ed-Fi / SIS
- Student Information Systems
- ·  Student enrollment and demographic data
- ·  Per-tenant adapter configuration
- ·  State-specific SIS implementations
- ·  Meal count and eligibility cross-reference
- ·  Ed-Fi data standards compliant
- FNS Policy Feeds
- USDA Federal Register
- ·  Federal Register API monitoring
- ·  Reimbursement rate updates
- ·  Daily automated check
- ·  Phase 2: LLM-assisted change classification
- ·  Human review before any platform update
- LaunchDarkly
- Feature Flag Service
- ·  47 module-level feature flags
- ·  Per-state flag configuration
- ·  Gradual rollout and A/B testing
- ·  Local cache in FlagDefs table
- ·  Zero-downtime feature activation

> **Speaker notes:** 100% write coverage — every save, submit, approve, reject, and override is captured automatically, with no opt-in required. Two layers working together: EntitySnapshots captures full state at each event, FieldChangeLog captures field-level deltas for every write. Append-only — no admin or script can modify or delete records. S3 Object Lock WORM storage for long-term retention. Point-in-time queryable — we can reconstruct the state of any record at any moment in its history. This is how we answer "who approved this claim and when?" for a federal auditor.


<!-- slide: 13 -->

## Slide 13

- Database Structure
- cnp_global single schema
- cnp_ops schema per state
- Aurora Postgresql single database
- Role per state that only has permissions on its own schema. Even if a query tried to cross schemas, the database would reject it.
- App resolves the tenant (state) at the start of every request from the authenticated user's session and constructs all queries against that state's schema.

> **Speaker notes:** We are not diving headfirst into microservices. The modular monolith lets us learn the right boundaries from real usage before we lock them into service contracts.

In a monolith, a wrong boundary is a namespace rename and moving some classes. In microservices, it's a new API contract, a data migration, and distributed transaction complexity.

Every domain is already namespace-isolated and schema-isolated. When the evidence says a domain needs independent scaling or deployment, we can extract it cleanly. The four authoritative domains — Claims, Accounting, Compliance, Eligibility — are the most likely candidates to move first. They have the clearest ownership and the most to gain from independent deployment.


<!-- slide: 14 -->

## Slide 14

| © EMS LINQ, LLC. All rights reserved. |
- Phase 2 – AI layer
- Every AI output requires human review before any platform action is taken.
- NLP Query Interface
- Authorized directors, finance staff, and VDOE administrators ask questions in plain English.
- Intent classified → parameters extracted → curated views queried → results returned.
- ⚠  Queries restricted to an approved catalog. No raw SQL. No PII in results.
- Risk Scoring AI
- Gradient-boosted model scores sponsors and sites for compliance risk before review selection.
- 6 signal groups · Nightly refresh · Quarterly retrain on outcomes. SHAP explainability shows top 3 factors.
- ⚠  Informational only.  Never auto-triggers a review. Human decides next step.
- Anomaly Detection
- Identifies unusual patterns in claims, DC match rates, and submission timing across the state.
- Claim spikes, disbursement outliers, late submission clusters — surfaced to state administrators.
- ⚠  No auto-actions. Flags are informational. A human decides what to do.
- New State Config Assist
- When onboarding a new state, AI scaffolds initial configuration by matching against similar existing states.
- POST /tenants/{code}/scaffold?similarTo= · Onshore team reviews and approves all suggestions.
- ⚠  Zero deployments to add a state. All suggestions require explicit onshore approval.
- EO 30 compliance: the NLP Query Interface must be registered with VITA via EA-225 before deployment. AI is a Phase 2 investment contingent on Phase 1 go-live.

> **Speaker notes:** All AI capabilities are Phase 2 — designed but not yet built. Every AI output requires human review before any platform action is taken.

Natural Language Processing Query Interface: plain-English questions from directors and finance staff, answered by querying curated Snowflake views. No raw SQL, no PII in results. Must be registered with VITA via EA-225 before deployment per Virginia EO 30.

Risk Scoring: gradient-boosted model scores sponsors and sites for compliance risk. SHAP explainability shows top 3 factors. Informational only — never auto-triggers a review.

Anomaly Detection: flags unusual patterns in claims, DC match rates, and submission timing. No auto-actions.

New State Config Assist: AI scaffolds initial configuration when onboarding a new state, matching against similar existing states. All suggestions require explicit onshore approval before anything is applied.

The human review gate is non-negotiable on all four capabilities.


<!-- slide: 15 -->

## Slide 15

- AWS Architecture

<!-- slide: 16 -->

## Slide 16

- Data Flow

<!-- slide: 17 -->

## Slide 17

- Q&A
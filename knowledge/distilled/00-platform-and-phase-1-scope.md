# The CNP platform, and what Phase 1 actually is

## The product {#product}

LINQ is building a net-new platform to administer USDA Child Nutrition Programs for state
agencies, replacing two legacy product lines at once: **CTS** (22+ states, cloud-based) and
**DIS** (6 states — AK, HI, ME, MO/DHSS, UT, WI — legacy WinForms desktop applications with
SFTP-based data collection). Twenty-eight states in total, served from a single codebase.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-11 -->

The unification of CTS and DIS from the start is a deliberate architectural decision, not a
sequencing accident. A CTS-only platform would leave DIS maintenance running indefinitely —
the exact cost the modernization exists to remove — and the federal compliance surface (FNS
programs, NDL, FNS reports) is identical between them. DIS-specific Direct Certification feed
collection is contained behind an `IDcFeedAdapter` interface rather than forking the platform.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-11 -->

## What to call it {#naming}

The platform was described at an offsite as a "BPM + ERP." That framing was **rejected for
engineering use**: BPM implies arbitrary process orchestration, when the workflow engine is
deliberately constrained by hard federal guardrails, and ERP implies a general ledger, when
the accounting layer is program-specific federal reimbursement math. Engineering
documentation says **"configurable federal nutrition compliance platform."** Executive and
nTIG communications may keep "BPM + ERP" where audience familiarity requires it. No single
document should serve both audiences.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-1 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-2 -->

The concrete risk named for the rejection is worth keeping: *"An engineer building a true BPM
engine to spec would produce a system with no federal guardrails."*
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-1 -->

## The three governing principles {#principles}

1. **Configurability has a hard boundary.** The platform is configurable up to the boundary
   of federal law. Anything mandated by federal regulation (CFR, USC, USDA policy) is
   implemented in code and protected by `IsFederal` guardrails. It cannot be exposed as a
   configuration surface regardless of how the request is framed.
2. **Vertical depth over horizontal breadth.** Purpose-built for CNP administration. Where a
   design choice trades "works for any program" against "works perfectly for SNP/CACFP/SFSP,"
   the latter wins.
3. **Framing must match audience.** See above.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-1 -->

## Phase 1 — the October prototype {#phase-1}

Phase 1 is **one state's SNP application-to-approval workflow, end to end, demonstrated
live** — real OIDC login, real database writes, real workflow engine, real federal compliance
controls. Not mocked, not simulated for the demo.
<!-- source: 00_FRD_Index.md#section-2 -->
<!-- source: CSN-Prototype-140826-133159.md#page-1 -->

What must be demonstrably real:

- OIDC login with real token issuance
- Workflow state machine evaluating actual named hook implementations
- The demo state's specific condition hook executing correctly
- A `ClaimLaws` row created in the database at approval — not a display trick
- Audit log entries written for every workflow transition, queryable in the database
- A config change propagating to the application layer within the cache TTL
- Role-based access enforced by the server, not just the UI
<!-- source: CSN-Prototype-140826-133159.md#page-1 -->

### Hard constraints {#constraints}

- One state only. No multi-state scenarios, no cross-state features.
- No production data anywhere. Synthetic or anonymized only.
- Offshore engineers work in the greenfield environment only, with no access to any existing
  LINQ system — not CTS, not DIS, not any current database, codebase or infrastructure. The
  design documents in the handover folder are their specification.
- **Claims workflow is out of scope.** The prototype ends at application approval. No claims,
  no FNS report generation, no reimbursement calculation beyond displaying the ClaimLaws
  freeze.
- The Configuration Admin UI is one screen for the speed demo, not a full admin application.
<!-- source: CSN-Prototype-140826-133159.md#page-1 -->

### The eight business functions {#business-functions}

| # | Business function | FRD | Feature coverage |
|---|---|---|---|
| 1 | Secure Multi-Tenant Identity & Access | FRD-01 | RF-01–RF-10, RF-41, RF-45 |
| 2 | Program & Tenant Configuration Management | FRD-02 | RF-30–RF-36 |
| 3 | Sponsor Application & Agreement Submission | FRD-03 | RF-11, RF-16, RF-17 |
| 4 | Application Review & Determination Workflow | FRD-04 | RF-12–RF-15, RF-18–RF-22 |
| 5 | Federal Disqualification Screening (NDL) | FRD-05 | RF-23–RF-26 |
| 6 | Regulatory Rate & Rule Freeze at Approval | FRD-06 | RF-27–RF-29 |
| 7 | Immutable Audit & Compliance Trail | FRD-07 | RF-35, RF-37–RF-40 |
| 8 | Secure, Compliant Delivery Foundation | FRD-08 | RF-41–RF-51 |
<!-- source: 00_FRD_Index.md#section-3 -->

### Deliberately deferred {#out-of-scope}

Claims processing, reimbursement calculation, FNS reporting, full NDL integration, multi-state
operation, and every program other than SNP. These are real business domains visible in the
legacy system, not gaps in the analysis: Claims & Reimbursement, Accounting & Finance,
Reviews, Eligibility & Direct Certification, the CACFP/SFSP/SSFO/FFVP/CEP program modules,
Budget, VCA Checklist, Food Distribution, Waivers, Training & Professional Standards.
<!-- source: 00_FRD_Index.md#section-2 -->
<!-- source: 00_FRD_Index.md#section-5 -->

## The document precedence rule {#precedence}

Stated twice, in the same words, in two independent places: **where a build plan and a design
document conflict, the design document wins — flag the conflict, do not resolve it silently.**
<!-- source: 00_FRD_Index.md#section-1 -->
<!-- source: CSN-Prototype-140826-133159.md#page-18 -->

This rule is the reason `99-contradictions-and-open-questions.md` exists in this corpus rather
than a set of quietly-chosen defaults.

## Why the legacy system cannot scale {#legacy-failure-modes}

Read out of the CTS and DIS repositories, five patterns:

1. **The same logic forks by state.** Missouri's federal report business-logic layer is already
   50% larger than Utah's — same form, same federal requirement, different file, because
   state-specific logic migrated into code instead of configuration.
2. **Business rules exist but do not run.** The CACFP Institution Management Plan has over 80
   compliance rules fully coded; the entire validation method is commented out and only one
   field is checked at submission. States have operated without that enforcement for years.
3. **Schema versions live in application code.** Hawaii's DC application tracks which database
   schema version it is talking to using hardcoded year constants that branch SQL queries.
   Three schema versions co-exist in production today.
4. **State-specific data is embedded in source.** SFTP IP addresses, plaintext credentials and
   PGP key file paths as string literals and `app.config` values — because there was no
   configuration system to put them in.
5. **Business logic is in the database and diverging.** SQL CLR functions for name matching,
   custom sequence generators, stored procedures encoding logic outside application
   visibility. The database has become a second application layer.
<!-- source: CSN-Data-140826-132933.md#page-2 -->

## A known blocker on legacy characterization {#encrypted-procs}

Several legacy stored procedures were **deliberately encrypted** to protect LINQ intellectual
property after incidents where states attempted to modify or redistribute the software. The
consequence is that the offshore team cannot characterize or reimplement what those
procedures do without seeing them. Two things are needed before those modules can be
sprinted: decrypted procedure source, and time from the engineers who originally built them.
The document is explicit that *"the offshore team can build from design documents. They
cannot build from institutional memory they don't have access to."*
<!-- source: CSN-Data-140826-132933.md#page-3 -->

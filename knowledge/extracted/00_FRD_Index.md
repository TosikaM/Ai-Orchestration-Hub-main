<!-- EXTRACTED from knowledge/inbox/00_FRD_Index.md on 2026-09-09T13:30:37Z -->
<!-- DO NOT EDIT. If extraction is wrong, fix the extractor and re-run. A
     hand-patched extraction no longer matches its source, and once that is
     true of one file no citation in this corpus can be trusted. -->

# CNP Platform Modernization — Phase 1 (October Prototype)
## Functional Requirement Documents — Index & Master Overview

**Version:** 0.1 (Draft)
**Date:** July 2026
**Status:** Derived from Program Planning outputs — for review against source design documents

---

## 1. Purpose of this document set

This FRD set answers one question: **what does the business get when Phase 1 ships?**

It is derived from three source materials:

- `Feature_List.xlsx` — 51 refined features (RF-01–RF-51) across 9 capability areas
- `CNP_Phase1_High-Level_Test_Plan.docx` — quality strategy, 13 test suites (TS-01–TS-13), demo-readiness DoD
- `CNP_Phase1_Test_Execution_Sprint_Plan.xlsx` — 83 scenarios (SC-101–SC-1303), sprint-by-sprint develop/execute cadence, full RF→suite→scenario traceability
- `CNP_ERD.html` — legacy CTS/DIS entity map (1,402 tables, 28 domains, 5 states) — the business/data reality Phase 1 replaces a slice of

Where this document and a customer design document conflict, **the design document wins** — same rule the Test Plan uses. Flag conflicts; don't silently resolve them.

**Scope note:** these FRDs describe **business functions**, not test scenarios. For the technical requirement-level detail (specific tables, triggers, API contracts) and full test traceability, see the companion Sprint Execution Workbook — this set deliberately does not duplicate that matrix.

---

## 2. What Phase 1 actually is

A live-demoed, working system running **one state's SNP (Special Nutrition Program) application-to-approval workflow end to end**, with real login, real database writes, and federal compliance controls enforced for real — not mocked, not simulated for the demo.

It is **not**: claims processing, reimbursement calculation, FNS reporting, full NDL integration, multi-state operation, or any program other than SNP. Those are real business domains (visible in the legacy ERD) that Phase 1 deliberately defers.

---

## 3. The 8 business functions

| # | Business Function | FRD | Primary RF Coverage | Primary Test Suite(s) |
|---|---|---|---|---|
| 1 | Secure Multi-Tenant Identity & Access | [FRD-01](01_FRD_Identity_Access.md) | RF-01–RF-10, RF-41, RF-45 | TS-01, TS-02, TS-11 |
| 2 | Program & Tenant Configuration Management | [FRD-02](02_FRD_Configuration_Management.md) | RF-30–RF-36 | TS-04, TS-07 (propagation), TS-10 |
| 3 | Sponsor Application & Agreement Submission | [FRD-03](03_FRD_Application_Submission.md) | RF-11, RF-16, RF-17 | TS-06 |
| 4 | Application Review & Determination Workflow | [FRD-04](04_FRD_Review_Workflow.md) | RF-12–RF-15, RF-18–RF-22 | TS-03, TS-06 |
| 5 | Federal Disqualification Screening (NDL) | [FRD-05](05_FRD_NDL_Screening.md) | RF-23–RF-26 | TS-05 |
| 6 | Regulatory Rate & Rule Freeze at Approval | [FRD-06](06_FRD_Rate_Freeze.md) | RF-27–RF-29 | TS-05, TS-06 |
| 7 | Immutable Audit & Compliance Trail | [FRD-07](07_FRD_Audit_Trail.md) | RF-35, RF-37–RF-40 | TS-07 |
| 8 | Secure, Compliant Delivery Foundation | [FRD-08](08_FRD_Delivery_Foundation.md) | RF-41–RF-51 | TS-08, TS-09, TS-11 |

Each FRD follows the same shape: Business Context → Actors → Functional Requirements → Business Rules → Assumptions & Constraints → Out of Scope → Dependencies → Acceptance Criteria → Cross-References.

---

## 4. Actors across the platform (referenced throughout)

| Role | Business Function |
|---|---|
| **Sponsor Director / Staff** | Organization representative; submits and manages SNP applications for their own organization only |
| **Caseworker** | State-side reviewer; performs first-pass review, advances or returns applications |
| **Reviewer** | State-side approver; makes the final approve/deny determination |
| **State Agency Admin** | State-level administrator; broader state-wide data visibility and oversight |
| **LINQ Config Admin** | Platform configuration administrator; manages tenant-level program settings |

Roles, scopes, and override behavior are fully specified in FRD-01.

---

## 5. Legacy domains explicitly out of scope for Phase 1

Cross-referenced against the CNP ERD's 28 legacy domains — these exist in the business today but are **not** part of the October Prototype:

Claims & Reimbursement, Accounting & Finance, Reviews (Instrument), Eligibility & Direct Cert, CACFP/SFSP/SSFO/FFVP/CEP program modules, Budget Module, VCA Checklist, Food Distribution/Commodity, Waivers, Training & Professional Standards, multi-state operation (CO/GA/IA/OH/WY — Phase 1 wires one demo state only).

These are real, sizeable domains (Food Distribution alone is 128 tables) — they represent the roadmap beyond Phase 1, not gaps in this analysis.

---

## 6. How to use this set

- Each FRD is reviewable and versionable independently.
- Cross-references to RF-IDs and TS-suites are pointers, not embedded requirements — pull the technical detail from the Sprint Execution Workbook when needed.
- These FRDs are the input for TDD: each Functional Requirement maps to one or more failing tests written before the corresponding build story starts.

## 7. TDD Plan

**[09_TDD_Plan.md](09_TDD_Plan.md)** — the developer-side, test-first companion to this FRD set. Organized by build sprint (Mobilization → Hardening & Demo), it maps every Functional Requirement across all 8 FRDs to a specific failing test to be written before implementation, cross-referenced to the existing QA scenario IDs (SC-101–SC-1303) so the developer-level test and the QA-level scenario stay in agreement.

## 8. Test Strategy

**[10_Test_Strategy.md](10_Test_Strategy.md)** — program-level quality approach: layers and ownership, risk focus, environments, sprint gates, and defect rules. It does not duplicate the QA scenario catalog or the TDD rows.

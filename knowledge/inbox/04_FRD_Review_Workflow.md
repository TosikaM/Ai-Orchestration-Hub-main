# FRD-04: Application Review & Determination Workflow

**Business Function 4 of 8** | **Version:** 0.1 (Draft) | **Status:** For Review

---

## 1. Business Context

Once a sponsor submits an application, it must move through a state-defined review process to a final determination: approved or denied. The business requirement that shapes this entire function is that **states differ in how they run this process**, and the platform must accommodate that difference through configuration — not through custom code per state. This is the single largest engineering bet in Phase 1: the review process itself is described as data, not hardwired as program logic.

## 2. Actors

Caseworker (first-line review), Reviewer (approval authority), State Agency Admin (oversight), Sponsor (receives outcomes and, where applicable, correction requests).

## 3. Functional Requirements

**FR-4.1 — Configurable review lifecycle.** An application moves through a defined sequence of states — from Draft through Submitted, Under Review, optionally Returned for correction, to a final Approved or Denied — where that sequence and the rules governing each step are defined as configuration, not application code.

**FR-4.2 — Only valid, permitted next steps are ever presented.** At any point in the process, a user only sees the actions they are both permitted to take (by their role) and that are valid for the application's current status — nothing else is offered, and nothing offered can actually fail due to being an invalid state change.

**FR-4.3 — A caseworker can advance or return an application.** A caseworker reviewing a submitted application can either move it forward for further/final review, or send it back to the sponsor with a required explanation of what needs correction.

**FR-4.4 — A returned application can be corrected and resubmitted.** A sponsor whose application was returned can make the requested corrections and resubmit it back into the review process.

**FR-4.5 — Approval requires satisfying all applicable federal pre-conditions.** Before an application can be moved to Approved, all federally-mandated checks that apply to it (see FRD-05) must pass. An approval cannot be granted by any means while a required check has not passed.

**FR-4.6 — Every step of the process is recorded.** Every time an application moves from one status to another — successfully or unsuccessfully — the system records who did it, when, what the change was, and the outcome of any checks involved (feeds directly into FRD-07).

**FR-4.7 — A state can customize its own review process without touching the shared, cross-state definition.** A state's specific customizations to the review process live in a state-specific override layer and never alter the shared baseline process other states rely on.

**FR-4.8 — Certain review steps are federally protected and cannot be removed or altered by a state.** Steps, rules, or checks that exist because of federal requirements (rather than state preference) cannot be disabled, skipped, or removed through state-level customization.

## 4. Business Rules

- A review step that fails its required condition halts the process at that point — the application does not advance, and no partial change is recorded as if it had.
- Every review action is tied to the specific user who performed it; there is no anonymous or system-attributed review action.
- An application in a final state (Approved or Denied) does not silently reopen — any need to revisit a final determination is a distinct, deliberate, and traceable action, not an ordinary workflow step.

## 5. Assumptions & Constraints

- Phase 1 implements exactly one program's lifecycle (SNP): Draft → Submitted → Under Review → (Returned) → Approved/Denied. The underlying mechanism is designed to support other programs' distinct lifecycles later, purely through configuration.
- The review process for the demo state is finalized as part of program planning; if a state-specific customization point (a review "hook") is not identified early enough, functionality is designed to remain flexible via a parameterized placeholder until it is.

## 6. Out of Scope (Phase 1)

Multi-level (beyond Caseworker → Reviewer) approval chains; automated/rules-based auto-approval without human review; appeals processes following a denial; multi-program review lifecycles beyond SNP.

## 7. Dependencies

- Depends on: Application Submission (FRD-03) as the entry point; Configuration Management (FRD-02) for the process definition itself; Federal Disqualification Screening (FRD-05) as a hard gate before approval; Identity & Access (FRD-01) for role-gated actions.
- Depended on by: Regulatory Rate & Rule Freeze (FRD-06), which triggers on approval; Audit Trail (FRD-07), which records every step.

## 8. Acceptance Criteria

- An application can be moved through the full lifecycle from submission to a final determination by the appropriate roles at each step.
- A caseworker can return an application with a required explanation, and the sponsor can correct and resubmit it.
- An approval cannot complete while a required federal check has not passed, through any interface or path.
- Every transition is fully attributable and time-stamped.
- A state-specific customization to the process does not affect any other state's process.

## 9. Cross-References

Feature List: RF-12, RF-13, RF-14, RF-15, RF-18, RF-19, RF-20, RF-21, RF-22.
Test Suites: TS-03 (Workflow Engine), TS-06 (Application Experience).

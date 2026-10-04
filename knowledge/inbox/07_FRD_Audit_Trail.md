# FRD-07: Immutable Audit & Compliance Trail

**Business Function 7 of 8** | **Version:** 0.1 (Draft) | **Status:** For Review

---

## 1. Business Context

A federally-regulated program must be able to answer, for any past action, "who did what, when, and what changed" — completely, accurately, and in a form that cannot itself be tampered with after the fact. This function is the connective tissue underneath every other business function in this document set: application submissions, review decisions, disqualification screenings, configuration changes, and rate freezes all feed into it. It exists as its own business function because the *guarantee* it provides — completeness and permanence — has to be true system-wide, not reinvented per feature.

## 2. Actors

The system itself (every other function feeds this one automatically); State Agency Admin / Reviewer / authorized oversight roles (consume the record, typically via the audit timeline); Config Admin (their configuration actions are also captured here, per FRD-02).

## 3. Functional Requirements

**FR-7.1 — Complete capture.** Every action anywhere in the system that changes something meaningful — an application's status, a configuration setting, a screening result, an approval — produces a corresponding record in the compliance trail. There is no category of consequential action that is silently excluded.

**FR-7.2 — Each record answers who, when, what, and the before/after detail.** Every audit record identifies the specific person who performed the action, the exact time it occurred, what kind of entity and action was involved, and — critically — what the affected data looked like both immediately before and immediately after the action.

**FR-7.3 — The trail is genuinely append-only.** Once a record is written, it cannot be edited or deleted by anyone, through any interface, including the most privileged administrative access. Correcting a mistake elsewhere in the system produces a *new* record; it never alters or removes a previous one.

**FR-7.4 — A human-readable timeline view.** For any given application, an authorized user can view its complete history as a single, plain-language, chronological timeline — not as raw technical log entries requiring interpretation.

**FR-7.5 — Failed and blocked actions are captured too, not just successful ones.** An action that was attempted but blocked (a validation failure, a permission denial, a compliance block) still produces a compliance record documenting the attempt and why it didn't succeed.

## 4. Business Rules

- A record's before/after content reflects the actual affected data at that moment — it is not reconstructed or inferred after the fact.
- Viewing the audit trail requires specific authorization; it is not open to every logged-in user by default.
- The completeness guarantee (FR-7.1) applies without exception to every business function described elsewhere in this document set — none of them are permitted to have an audit gap.

## 5. Assumptions & Constraints

- "100% capture" is validated in Phase 1 specifically against the demo's SNP application-to-approval flow; broader system-wide completeness is expected to be continuously verified as new functionality is added in later phases.

## 6. Out of Scope (Phase 1)

Long-term archival/retention policy tooling beyond the append-only guarantee itself; automated compliance reporting or export beyond the on-screen timeline view; search/analytics across the audit trail at scale.

## 7. Dependencies

- Depended on by (feeds from): Application Submission (FRD-03), Application Review Workflow (FRD-04), Federal Disqualification Screening (FRD-05), Rate Freeze (FRD-06), Configuration Management (FRD-02) — every one of these produces records here.
- Depends on: Identity & Access (FRD-01), to correctly attribute every record to a real, authenticated actor.

## 8. Acceptance Criteria

- Every consequential action anywhere in the demonstrated flow produces a complete, attributable audit record.
- No audit record can be altered or removed by any user, including administrators.
- An authorized user can view a complete, human-readable history for any given application.
- A blocked or failed action still produces an audit record documenting the attempt.

## 9. Cross-References

Feature List: RF-35, RF-37, RF-38, RF-39, RF-40.
Test Suites: TS-07 (Audit & Immutability).

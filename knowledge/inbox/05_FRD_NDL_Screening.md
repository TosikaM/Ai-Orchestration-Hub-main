# FRD-05: Federal Disqualification Screening (National Disqualified List)

**Business Function 5 of 8** | **Version:** 0.1 (Draft) | **Status:** For Review

---

## 1. Business Context

Federal program rules prohibit approving a sponsor organization (or its named principals) that has been federally disqualified from participation. This is a legal compliance requirement, not a business preference — which is why it is treated throughout this document set as an absolute, non-negotiable gate rather than an ordinary business rule. In Phase 1, the actual federal disqualification list is represented by a realistic stand-in dataset (since live integration with the real federal source is a later-phase concern), but the blocking behavior and compliance record it produces must be completely real and demo-representative.

## 2. Actors

Reviewer (triggers the approval action that invokes screening), State Agency Admin / designated reviewer (handles cases requiring human judgment), the screening check itself (an automated, non-human gate).

## 3. Functional Requirements

**FR-5.1 — Automatic screening on every approval attempt.** Every single time an approval is attempted for an application, the sponsoring organization, its tax ID, and its named responsible individuals are automatically checked against the federal disqualification list. This check is not optional, not skippable, and runs fresh every time — a previous pass does not exempt a later attempt.

**FR-5.2 — Three possible outcomes.** Every screening produces one of exactly three outcomes: **No Match** (approval may proceed), **Possible Match** (requires human review before proceeding), or **Confirmed Match** (approval is permanently blocked).

**FR-5.3 — A confirmed match is an absolute block.** When the outcome is Confirmed Match, no user, no administrator, no configuration setting, and no override mechanism of any kind can allow that application to be approved. This is the strongest guarantee in the entire platform — stronger even than the general permission-override model in FRD-01, because it cannot be reached through any override layer at all.

**FR-5.4 — A possible match routes to human review, not an outright block.** When the outcome is Possible Match, the application does not automatically fail, but it also does not automatically proceed — it is routed to a designated reviewer who examines the specifics and makes an explicit decision to approve or deny the override, which is itself recorded.

**FR-5.5 — Every screening attempt is permanently recorded**, regardless of outcome — including the specific data checked and the result — as part of the compliance record (see FRD-07).

**FR-5.6 — The screening data source can be a realistic substitute in Phase 1, but the behavior around it must be indistinguishable from the real thing.** Using a stand-in dataset instead of the live federal source is acceptable for now; treating a match against it any differently than a match against the real source is not.

## 4. Business Rules

- The screening check cannot be bypassed by any workflow shortcut, batch action, or administrative override — including for state-level admins.
- A reviewer who is also the one who submitted the application (in any capacity) is not permitted to be the one to clear a Possible Match on it — this check exists to protect the integrity of the review itself.
- The specific criteria that produced a match (organization name, tax ID, or a named individual) is recorded, not just the fact that a match occurred.

## 5. Assumptions & Constraints

- Phase 1 uses a synthetic/stub disqualification dataset by design — this is explicitly acceptable and does not weaken the compliance requirement, since the blocking logic and audit trail are real regardless of the data source.
- Full integration with the live federal disqualification data source is out of scope for Phase 1 and is flagged as a defined item for later-phase planning.

## 6. Out of Scope (Phase 1)

Live integration with the actual federal disqualification data feed; automated appeal or dispute resolution for a confirmed match; time-aware historical disqualification status changes.

## 7. Dependencies

- Depends on: Application Review Workflow (FRD-04), which triggers screening as part of the approval step; Identity & Access (FRD-01) for reviewer authorization and segregation-of-duties enforcement.
- Depended on by: Regulatory Rate & Rule Freeze (FRD-06), which only occurs after a successful (non-blocked) approval.

## 8. Acceptance Criteria

- Every approval attempt triggers a fresh screening check with no exceptions.
- A confirmed match cannot be overridden through any interface, role, or direct technical path.
- A possible match is routed for human decision and cannot silently auto-resolve either way.
- Every screening attempt, regardless of outcome, is permanently recorded with the specific match criteria.

## 9. Cross-References

Feature List: RF-23, RF-24, RF-25, RF-26.
Test Suites: TS-05 (Federal Controls & Guardrails).

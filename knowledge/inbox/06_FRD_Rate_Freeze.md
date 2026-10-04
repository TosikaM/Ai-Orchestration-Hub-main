# FRD-06: Regulatory Rate & Rule Freeze at Approval

**Business Function 6 of 8** | **Version:** 0.1 (Draft) | **Status:** For Review

---

## 1. Business Context

The specific reimbursement rates and eligibility rules that apply to a sponsor can change over time — a rate schedule updates, a policy is revised. But once an application has been approved under a particular set of rules, that sponsor's legal entitlement is defined by the rules **as they existed at the moment of approval**, not whatever rules happen to be in effect later. This function exists to permanently preserve that exact moment-in-time snapshot, so the organization always has a defensible, unambiguous record of what applied to their approval — independent of anything that changes afterward.

## 2. Actors

The system itself (this is an automatic, non-human-triggered function that fires as a consequence of approval); Reviewer/State Agency Admin (view the resulting frozen record); Sponsor (sees their own frozen record).

## 3. Functional Requirements

**FR-6.1 — A permanent snapshot is created automatically on approval.** The moment an application is approved (see FRD-04), the system automatically captures and permanently stores the specific eligibility rules and rates that were in force at that exact moment, tied to that specific application.

**FR-6.2 — The snapshot is genuinely permanent — it cannot be edited or deleted, by anyone.** Once created, this record cannot be changed or removed through any interface or administrative capability. There is no "correct a mistake" edit path — a genuine correction requires a new, separately recorded action, never a silent change to the frozen record itself.

**FR-6.3 — Later rule or rate changes never retroactively affect an existing frozen record.** If the underlying rates or rules are updated after an approval, every previously approved application's frozen snapshot remains exactly as it was at approval time — completely unaffected by the later change.

**FR-6.4 — The frozen record is visible to relevant users after approval.** An approved application's frozen rate/rule snapshot is clearly viewable on the application's record — not just stored invisibly in the background.

**FR-6.5 — One mechanism serves every program, driven by configuration.** The freezing capability itself is built once, generically, and works for any program type through configuration — not as separate, duplicated logic per program. This directly replaces what today are multiple separate, program-specific procedures for accomplishing the same underlying business need.

## 4. Business Rules

- The frozen snapshot always reflects the rules genuinely in force at the literal moment of approval — not the moment the application was submitted, not the moment it was reviewed.
- No user role, including the most privileged administrative role, has a "delete" or "edit" capability over an existing frozen snapshot.
- The values shown to a user viewing the frozen snapshot must exactly match what was actually stored — there is no separate "display" version that could drift from the stored record.

## 5. Assumptions & Constraints

- Phase 1 demonstrates this mechanism against the SNP program only, but it is explicitly designed to be reused, unmodified, by future program types added to the platform.

## 6. Out of Scope (Phase 1)

Automated re-calculation or reconciliation against a frozen snapshot; historical bulk reporting across many frozen snapshots (e.g., FNS-style reporting); a formal "correction" workflow for an erroneous freeze (a business process decision for a later phase).

## 7. Dependencies

- Depends on: Application Review Workflow (FRD-04), which is the sole trigger for this function; Configuration Management (FRD-02), which defines the rates/rules being snapshotted.
- Depended on by: Audit Trail (FRD-07), which further reinforces the immutability guarantee described here.

## 8. Acceptance Criteria

- Every approval produces exactly one corresponding frozen snapshot, with no exceptions and no delay.
- An attempt to modify or delete an existing frozen snapshot is rejected through every available path.
- A frozen snapshot remains unchanged even after the underlying rates/rules are later updated.
- The frozen snapshot is visible on the application record with values matching the stored record exactly.

## 9. Cross-References

Feature List: RF-27, RF-28, RF-29.
Test Suites: TS-05 (Federal Controls & Guardrails), TS-06 (Application Experience — E2E, frozen-rate display).

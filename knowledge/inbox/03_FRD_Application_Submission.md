# FRD-03: Sponsor Application & Agreement Submission

**Business Function 3 of 8** | **Version:** 0.1 (Draft) | **Status:** For Review

---

## 1. Business Context

The core sponsor-facing capability of Phase 1: an organization applies annually to participate in the SNP program. Today this process happens through the legacy system's application intake; Phase 1 rebuilds it as a modern, guided, server-driven form that the state can adjust without a developer rebuilding the screen every time a field needs to change.

## 2. Actors

Sponsor Director/Staff (primary user — completes and submits), Caseworker/Reviewer/State Agency Admin (consume the submitted application downstream — see FRD-04).

## 3. Functional Requirements

**FR-3.1 — Sponsor-scoped application list.** A sponsor user sees a list of applications belonging only to their own organization — never another organization's, regardless of what state they're in.

**FR-3.2 — Guided annual application form.** A sponsor can open, complete, and submit the annual SNP application through a structured, guided form.

**FR-3.3 — The form's structure is defined by the state, not hardcoded per screen.** The specific fields, their order, and their requiredness on the application form are defined centrally and rendered dynamically — meaning the state (via configuration, not a developer) controls what the form actually asks, and a field can be added or changed without a new release of the application.

**FR-3.4 — In-progress work is saved.** A sponsor who starts an application, leaves partway through, and returns later finds their previously entered information intact and editable — nothing is lost.

**FR-3.5 — Submission requires completeness.** A sponsor cannot submit an incomplete application; the system clearly identifies what's missing or invalid before submission is allowed.

**FR-3.6 — Validation failures are visible and, where policy allows, correctable by state staff.** If a submission fails validation, the specific failure is recorded and shown to the sponsor. In some cases, state-side staff may be permitted to override a specific validation failure on the sponsor's behalf — but only where that override has been explicitly allowed by configuration (see FRD-02, FR-2.4 for the federal-lock exception to this).

## 4. Business Rules

- Only the sponsor organization that owns an application (and authorized state staff, per FRD-01) can view or edit it.
- A submitted application is time-stamped and attributed to the submitting user for the record.
- The application form cannot silently drift from what the state has configured it to be — what a sponsor fills out always matches the state's current, approved form definition.

## 5. Assumptions & Constraints

- Phase 1 covers exactly one program type (SNP) and one demo state's specific form configuration; the mechanism is designed to extend to other programs and states without rebuilding the form-rendering approach itself.
- Structural validation is prioritized in Phase 1; deep, program-specific business-rule validation may be minimal for the October demo and is expected to deepen in later phases.

## 6. Out of Scope (Phase 1)

Multi-program application types beyond SNP; multi-year application history/renewal automation beyond the current annual cycle; document/attachment upload as part of the application (unless explicitly configured in scope for the demo).

## 7. Dependencies

- Depends on: Identity & Access (FRD-01) for sponsor authentication and data scoping; Configuration Management (FRD-02) for the form definition itself.
- Depended on by: Application Review & Determination Workflow (FRD-04), which consumes the submitted application.

## 8. Acceptance Criteria

- A sponsor can view only their own organization's applications.
- A sponsor can complete, save, resume, and submit the SNP annual application.
- The rendered form matches the state's current form definition exactly, with no hardcoded fields.
- An incomplete or invalid submission is blocked with a clear, specific reason.

## 9. Cross-References

Feature List: RF-11, RF-16, RF-17.
Test Suites: TS-06 (Application Experience).

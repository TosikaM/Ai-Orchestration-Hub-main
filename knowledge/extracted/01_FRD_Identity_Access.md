<!-- EXTRACTED from knowledge/inbox/01_FRD_Identity_Access.md on 2026-09-09T13:30:37Z -->
<!-- DO NOT EDIT. If extraction is wrong, fix the extractor and re-run. A
     hand-patched extraction no longer matches its source, and once that is
     true of one file no citation in this corpus can be trusted. -->

# FRD-01: Secure Multi-Tenant Identity & Access

**Business Function 1 of 8** | **Version:** 0.1 (Draft) | **Status:** For Review

---

## 1. Business Context

The platform serves multiple state agencies from one shared system, with each state's data and users strictly isolated from every other state's. Phase 1 wires one demo state, but the login, tenant-resolution, and access-control model must be built as if every state were live — because it will be, in later phases.

Every person who touches the system — a sponsor submitting an application, a caseworker reviewing it, a state admin configuring program rules — must be authenticated for real, scoped to exactly their state and role, and prevented from ever seeing another state's data, regardless of what they click, type into a URL, or call directly via API.

## 2. Actors

Sponsor Director/Staff, Caseworker, Reviewer, State Agency Admin, LINQ Config Admin — see FRD Index §4 for role definitions. All five roles authenticate through the same identity mechanism described here; what differs is what they're authorized to see and do once in (covered operationally in each downstream FRD).

## 3. Functional Requirements

**FR-1.1 — Real single sign-on.** Users log in through a real identity provider (not a mocked or stubbed login) using an industry-standard protocol. There is no path in the product, including test/demo builds, where a fabricated identity token grants access.

**FR-1.2 — State-scoped access by subdomain.** Each state agency accesses the platform through its own web address. The system automatically determines which state's data and rules apply based on that address — a user never has to manually select or declare their state.

**FR-1.3 — Minimal, non-sensitive session tokens.** The credential a user's browser holds after login identifies their role and their state — nothing more. It never carries a raw, expanded list of what that user can do (that's determined fresh, server-side, on every action — see FR-1.5). The credential lives only in the browser's active session memory; it is never written to persistent browser storage, so it cannot be recovered after the browser is closed or by inspecting saved site data.

**FR-1.4 — Layered, overridable role permissions with a hard safety valve.** What a role can do is determined by three layers of configuration, from most general to most specific, with the most specific layer winning. However: an explicit "this is not allowed" instruction at any layer always wins over a "this is allowed" instruction at a broader layer, regardless of specificity. This ensures a state can always lock something down further than the platform default, but never accidentally loosen a restriction that was deliberately imposed at a broader level.

**FR-1.5 — Every access decision is re-checked, server-side, every time.** No screen, button, or link being hidden from a user is ever treated as the actual security control. Every single action a user takes is independently re-validated against their current permissions on the server before it's carried out — a user cannot gain access by bypassing the visual interface.

**FR-1.6 — Certain permissions cannot be taken away by anyone.** A small set of permissions tied to federal program requirements are locked at the platform level and cannot be revoked or weakened by any state, admin, or configuration override — see FR-1.4's override model; this is the one case where even an explicit state-level restriction does not apply.

**FR-1.7 — Data visibility is scoped automatically, not by convention.** A user's visible data (e.g., "my organization's applications only" vs. "every application in the state") is enforced automatically based on their assigned scope — it is not something that depends on the application screen being built correctly; it is guaranteed at the data-access layer itself.

**FR-1.8 — Five demo roles with distinct, documented capabilities.** Sponsor Director/Staff, Caseworker, Reviewer, State Agency Admin, and LINQ Config Admin each have a clearly defined, distinct set of capabilities appropriate to their real-world job function. A user can hold more than one role.

## 4. Business Rules

- A login session that has gone stale must be re-established through the real identity provider — there is no silent, automatic renewal that bypasses re-authentication.
- If the identity provider is unreachable, no user can log in — there is no fallback authentication path.
- A permission check that cannot be completed (due to a system error) always results in access being denied, never access being granted by default.
- A user with no assigned role/scope sees no data — never an error that reveals system internals, and never a default of "see everything."

## 5. Assumptions & Constraints

- Phase 1 wires exactly one state's identity realm; the architecture must not require code changes to add a second state later (configuration only).
- The specific identity provider platform was an open decision at program start and had to be finalized before build began; downstream requirements here are written to be provider-agnostic.

## 6. Out of Scope (Phase 1)

Multi-state identity federation (only one state realm is actually wired, though the mechanism supports more); self-service password reset flows beyond what the identity provider provides out of the box; identity provider migration/failover.

## 7. Dependencies

- Depends on: the platform/tenant data-boundary model (FRD-08) — a user's state scope must map cleanly to a data boundary.
- Depended on by: every other business function — nothing else in the system is reachable without this.

## 8. Acceptance Criteria

- A real user can log in through the real identity provider and reach their role-appropriate landing screen.
- A user from State A cannot, by any means (UI navigation, direct link, direct API call), view or act on State B's data.
- A user attempting an action outside their permission set is denied at the server, with a clear, non-technical-sounding message.
- A federally-locked permission remains enforced even when a state admin attempts to override it.
- No session credential is ever recoverable from persistent browser storage after the session ends.

## 9. Cross-References

Feature List: RF-01, RF-02, RF-03, RF-04, RF-06, RF-07, RF-08, RF-09, RF-10, RF-41, RF-45.
Test Suites: TS-01 (Security & Authentication), TS-02 (Authorization/RBAC), TS-11 (Security Testing — cross-tenant isolation, token handling).

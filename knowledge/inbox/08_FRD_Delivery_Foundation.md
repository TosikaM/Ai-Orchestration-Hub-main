# FRD-08: Secure, Compliant Delivery Foundation

**Business Function 8 of 8** | **Version:** 0.1 (Draft) | **Status:** For Review

---

## 1. Business Context

This function is different from the other seven: it's not a capability an end user directly experiences, but it's the business precondition that makes the other seven trustworthy at all. Two business realities drive it: (1) the platform is being built net-new, replacing a large legacy footprint (1,402 tables across 28 domains in the current system), and it must be architected so future states and programs can be added without re-architecting; and (2) the build itself is being delivered by a distributed team that includes offshore engineers, which creates its own, separate data-handling and access obligations that must be structurally enforced — not just policy on paper.

## 2. Actors

DevOps/Platform team (provisions and operates the environments), Onshore Technical Lead (approves sensitive changes and access), Configuration Specialist (signs off the demo environment), Offshore engineering team (subject to the access restrictions this function defines), Data Engineer role (builds the underlying schema/architecture).

## 3. Functional Requirements

**FR-8.1 — Tenant data isolation is a database-level guarantee, not an application-level convention.** Each state's operational data lives in its own database boundary, separate from every other state's, and separate from the shared reference data every state draws from. This isolation is the actual enforcement mechanism behind the access guarantees described in FRD-01 — it does not rely on application code remembering to filter correctly.

**FR-8.2 — Schema changes are managed, tracked, and reversible — never ad hoc.** Every change to the underlying data structure goes through a tracked, versioned change process. There is no path for an untracked, one-off structural change to reach any environment.

**FR-8.3 — The system is built only as large as the current business need requires.** Rather than building out every conceivable future data domain up front, the platform is scoped to what the demonstrated business flow actually needs now, with clearly marked placeholders for future domains — avoiding both wasted build effort and premature complexity.

**FR-8.4 — Sensitive credentials are never exposed in code, configuration files, or logs.** Every credential or secret the system needs to operate is retrieved through a single, centrally managed secure mechanism at the moment it's needed — never hardcoded, never stored in plain text anywhere a person could stumble across it.

**FR-8.5 — Offshore engineering access is structurally restricted to non-sensitive environments and synthetic data only.** Any environment an offshore team member can reach contains only realistic but entirely fictional data — never real program participant information — and this is independently verified, not just assumed from policy. Offshore access does not extend to the environments used for the live demonstration or for state user testing.

**FR-8.6 — Environments are tiered by sensitivity and access level.** Development and shared testing environments are more broadly accessible; the environments used for the live demonstration and for state-facilitated testing are isolated, more tightly controlled, and require deliberate, approved deployment.

**FR-8.7 — Before any live demonstration, a qualified person formally confirms the environment is ready.** A designated, authorized person reviews and signs off on the demonstration environment — including confirming no real program data is present — before it is used in front of external stakeholders.

## 4. Business Rules

- No production or real state participant data exists anywhere in a non-production environment, under any circumstance, for any reason including debugging.
- A structural change to the data model always goes through the tracked change process, even for urgent fixes.
- Any environment or access grant given to the offshore team is independently verifiable against the restrictions in FR-8.5 — it is not sufficient that the restriction was merely intended.

## 5. Assumptions & Constraints

- The choice of underlying identity, cloud, and technology platform components was finalized at the start of delivery and is treated here as a settled foundation, not an open question.
- The final scope of the data model (how many tables, which domains) is expected to grow through delivery; Phase 1 validates the *approach* (managed, minimal, extensible) rather than a fixed final count.

## 6. Out of Scope (Phase 1)

Multi-region or disaster-recovery infrastructure (explicitly flagged as a future-phase requirement); full production-scale performance/load infrastructure; onboarding additional states' infrastructure beyond the one demo state.

## 7. Dependencies

- Depended on by: every other business function in this set — this is the structural foundation all of them run on.

## 8. Acceptance Criteria

- No real program participant data is ever present in any environment reachable by the offshore team.
- Every structural data change traces to a tracked, versioned change record.
- No credential is discoverable in code, configuration, or logs at any point.
- The demonstration environment has documented, dated sign-off from an authorized reviewer before any live demonstration.
- A state's operational data cannot be reached from another state's context by any technical means.

## 9. Cross-References

Feature List: RF-41, RF-42, RF-43, RF-44, RF-45, RF-46, RF-47, RF-48, RF-49, RF-50, RF-51.
Test Suites: TS-08 (Data & Architecture), TS-09 (Environments & DevOps), TS-11 (Security Testing — secrets hygiene).

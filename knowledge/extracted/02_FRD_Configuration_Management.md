<!-- EXTRACTED from knowledge/inbox/02_FRD_Configuration_Management.md on 2026-09-09T13:30:37Z -->
<!-- DO NOT EDIT. If extraction is wrong, fix the extractor and re-run. A
     hand-patched extraction no longer matches its source, and once that is
     true of one file no citation in this corpus can be trusted. -->

# FRD-02: Program & Tenant Configuration Management

**Business Function 2 of 8** | **Version:** 0.1 (Draft) | **Status:** For Review

---

## 1. Business Context

Every state runs the same federal nutrition program under the same federal rules, but each state also has legitimate latitude to set its own operational details — deadlines, thresholds, wording — within those federal boundaries. Today, this kind of customization typically requires a code change and a deployment. The business goal here is to eliminate that: a state's own authorized staff can change a setting themselves and see it take effect across the live system within minutes, with zero developer involvement, while anything federally mandated remains completely un-touchable no matter who tries.

## 2. Actors

LINQ Config Admin (makes changes), State Agency Admin (may also have limited config visibility/rights depending on role setup), all downstream users of the platform (experience the effect of a change immediately, whether they know it or not).

## 3. Functional Requirements

**FR-2.1 — Three-layer, most-specific-wins configuration.** Every configurable setting resolves through three layers — a platform-wide default, an optional program-level override, and an optional state (tenant)-level override — with the most specific layer that has a value always winning.

**FR-2.2 — Every setting is validated, not free-text.** Every configurable value has a defined data type and, where meaningful, a defined valid range or set of allowed values. An attempt to set a value outside that range, or of the wrong type, is rejected at the moment it's saved — never silently accepted and only discovered later as a runtime failure.

**FR-2.3 — Every override requires a stated reason and an effective date.** No setting can be changed anonymously or without explanation. Every override records who changed it, when it takes effect, and why. A change can be scheduled to take effect on a future date without requiring anyone to be present or to deploy anything on that date.

**FR-2.4 — Federally-mandated settings cannot be overridden by anyone, at any layer, through any path.** A subset of settings are flagged as federally locked. No state, no admin, and no configuration screen — nor any behind-the-scenes technical path — can change these. This is enforced independently at more than one layer of the system, so that even a technical error elsewhere cannot accidentally allow a federal setting to be changed.

**FR-2.5 — Changes are visible live, in minutes, without a deployment.** An authorized admin changes a setting through an administrative screen, and the effect is observable across the live system in a matter of minutes — not hours, not after the next release.

**FR-2.6 — Every configuration change is logged.** Every single change to a setting — successful or not — is recorded with enough detail to answer "who changed what, from what, to what, when, and why" at any later point.

**FR-2.7 — Select platform capabilities can be turned on/off independently per module.** A small number of major platform modules can be enabled or disabled centrally, affecting both what's available on screen and what the underlying system will accept, consistently.

## 4. Business Rules

- The single most specific applicable layer always wins; layers do not "blend" or average.
- A federally-locked setting shows as read-only to every user in every administrative interface, with a clear indication of why (a citation or reference, not just "locked").
- Repeated rapid changes to the same setting by the same admin are rate-limited, to prevent a runaway or automated misuse of the live-propagation capability.
- A rejected (invalid) change attempt never appears in the record of what's currently in effect — only successful changes take effect, but every attempt (successful or not) still generates a compliance record per FR-2.6.

## 5. Assumptions & Constraints

- The full catalog of configurable settings grows over the course of delivery; Phase 1 validates the resolution mechanism and administrative experience against whatever subset is seeded by the relevant sprint, not a fixed final catalog.
- "Minutes" for live propagation is a demo-scale target on the demo environment; broader production-scale propagation performance is a later-phase concern.

## 6. Out of Scope (Phase 1)

A full self-service settings catalog covering every conceivable program parameter; configuration change approval workflows (multi-person sign-off before a change takes effect); configuration rollback/versioned restore beyond the change history itself.

## 7. Dependencies

- Depends on: Identity & Access (FRD-01) — only authorized roles can reach the admin screen.
- Depended on by: Application Review Workflow (FRD-04), which consumes many of these settings; Audit Trail (FRD-07), which records every change.

## 8. Acceptance Criteria

- An authorized admin can change a non-federal setting and see its effect live elsewhere in the system within the target time window.
- An attempt to change a federally-locked setting is rejected through every available path, with the reason clearly stated.
- A setting with no state-specific or program-specific override falls back correctly to the platform default.
- Every change (accepted or rejected) is fully attributable after the fact.

## 9. Cross-References

Feature List: RF-30, RF-31, RF-32, RF-33, RF-34, RF-35, RF-36.
Test Suites: TS-04 (Configuration Engine), TS-07 (propagation/audit), TS-10 (propagation timing).

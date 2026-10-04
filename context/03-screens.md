<!-- PROJECT CONTEXT — synthesised, not a source document.

     Every factual claim here needs a provenance comment naming where it came from:
         <!-- from: knowledge/distilled/<topic>.md#<anchor> -->
     `python scripts/project-context.py check` fails on a claim without one.

     If a statement has no source, it is an ASSUMPTION. Move it to 06-open-questions.md
     with the assumption stated, rather than leaving it here where the next reader will
     take it for a requirement. -->

# Screens

Six screens were delivered as paired HTML mockups and PNG renders. **All six are sponsor-facing.
No state-side screen exists in this handover** — no caseworker review queue, no reviewer
determination screen, no audit timeline (RF-39, 48h), no Config Admin screen (RF-34, 60h).
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-1 -->
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#effort -->

## The shell {#shell}

Every authenticated screen shares one chrome: a persistent 240px navy sidebar — **Dashboard,
Applications, Sites, Documents, Notifications (badged), Reports, Audit History**, with Help and
Sign Out pinned at the bottom — and a top utility bar carrying a **Program** selector
(NSLP/SBP/SFSP/CACFP), a **Program Year** selector (2026-27/2025-26/2024-25), a notification
bell, and a user/role chip.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#shell -->

Program and program year as **global context selectors** rather than per-page filters is a
structural decision, and it matches the frontend architecture, where program year is a URL path
segment (`/:programYear/applications/:program/:formType`) specifically so concurrent tabs
across program years do not conflict. Tenant is resolved from the subdomain, never the URL.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#shell -->
<!-- from: knowledge/distilled/09-infrastructure-and-environments.md#forms -->

## Inventory {#inventory}

| # | Screen | Purpose | Primary actions |
|---|---|---|---|
| 1 | Login (SSO) | Authenticate at the identity provider | Sign in with SSO |
| 2 | Sponsor dashboard | Where do my applications stand; what needs me | Start New Application; Open |
| 3 | Application packet overview | Completeness hub for one application | Validate Application; Submit for Approval |
| 4 | Sponsor application form | The 7-section application wizard | Save Draft; Save & Continue; Validate |
| 5 | Site applications summary | Read-oriented view of all site applications | Manage Site Applications |
| 6 | Site application list | The working list — add, import, filter, bulk-select | Import Sites; Add Site Application |
<!-- from: knowledge/distilled/11-screens-and-design-system.md#inventory -->

## Flow {#flow}

```
  [1] Login ──> [2] Dashboard ──"Start New Application"──> [4] Application form
                     │                                            ▲   │
                     │  Open / View all                           │   │ View Packet Overview
                     ▼                                            │   ▼
              [3] Packet overview ──"View" (Sponsor Application)──┘
                     │
                     ├──"Manage Sites"──> [5] Site summary ──"Manage"──> [6] Site list
                     ├──"Manage Documents"──> (not designed)
                     ├──"View Validation"────> (not designed)
                     └──"Submit for Approval" ──> state-side review (no screens supplied)
```
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-3 -->
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screens-5-6 -->

Three destinations are linked from the delivered screens and were not designed: the validation
results view, document management, and everything after Submit.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-3 -->

## Status vocabulary {#statuses}

Eight application-level statuses, consistent between the dashboard and the design system:
**Draft · Ready to Submit · Under Review · Returned (for Correction) · Approved · Denied ·
Withdrawn · Closed** — plus **In Progress** at packet level and **Attention** at site level.

The UI uses **Denied**, matching the FRDs and feature list, rather than the prototype plan's
**Declined**.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#status-vocabulary -->

Each status has a strict colour pairing — text colour on a tint with a border — so a status is
identifiable without reading it.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#colours -->

## Form structure {#form-structure}

Seven sections: Organization Information · Contact Information · Program Information ·
Eligibility · Certifications & Assurances · Additional Information · Review & Submit.

**Only section 1 has a field inventory** — 13 fields across Organization Details and Primary
Address, eight of them required. Sections 2–7 are named and otherwise unspecified, which is a
problem because RF-17 requires the entire form to be server-supplied metadata.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-4 -->

The form supports both autosave ("Autosaved: 2 min ago") and an explicit **Save Draft**, and an
explicit **Validate** action separate from Submit — which is the correct rendering of the
requirement that submission is blocked with a clear, specific reason.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-4 -->
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-3 -->

Five field states are specified by the frontend architecture: Required, Optional, Hidden (not
in the DOM, value reset to null, skipped entirely by validation), Read-Only (visible, not
editable, **server still validates on submit**), and Conditional.
<!-- from: knowledge/distilled/09-infrastructure-and-environments.md#forms -->

## States that are missing across every screen {#missing-states}

The handover renders only the populated, happy-path state. Sprint 5's gate requires loading,
error and empty states to be handled with no console errors, and none of them are designed.

| Missing state | Where it matters most |
|---|---|
| **Empty** | The dashboard a brand-new sponsor sees first — all eight cards at zero; and the site list before any site exists, which is where Import and Add live |
| **Field validation errors** | Screen 4 — the design system specifies an error treatment, and no screen shows one |
| **Read-only fields** | Screen 4 — Iowa's documented configuration sources addresses from the state EIS and renders them read-only, with no design for how that is explained |
| **Submitted / Under Review / Returned** | Screen 3 — what a sponsor sees once the application has left their hands, and how a caseworker's required explanation surfaces |
| **Selected rows** | Screen 6 has checkboxes and select-all with no bulk action bar |
| **Import in progress / partial failure** | Screen 6 — a bulk import of school sites will partially fail routinely |
| **IdP unreachable / no role assigned** | Screen 1 — both have defined requirement behaviour and no design |
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-2 -->
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-4 -->
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#sprint-5 -->

## Design system {#design-system}

"Public Trust Modern" — an authoritative public-sector aesthetic on three tenets: institutional
trust and rigor, **WCAG 2.1 AA accessibility**, and operational clarity for dense regulatory
workflows. Colour is used strictly for semantic communication, not ornament.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#design-system -->

- **Primary Navy `#0B2A56`** structure; **Royal Blue `#0D52B7`** interaction; neutral greys for
  layered surfaces on an `#F4F6F9` canvas.
- **Public Sans** headlines, **Source Sans 3** body — the latter chosen for legibility at 11–12px
  in dense tables. Numerics use tabular figures for column alignment.
- 12-column grid; sidebar 240px desktop, 64px icon rail tablet, off-canvas drawer mobile, where
  **dense tables convert to vertical stacked cards.**
- Elevation favours **boundary clarity over drop shadows** — an explicit accessibility choice
  for well-lit office environments.
- Every focused element gets a **dual focus ring** (`0 0 0 2px #FFFFFF, 0 0 0 4px #0D52B7`) so
  focus stays visible against any background.
- Minimum 40px interactive target height, 44px on touch.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#colours -->
<!-- from: knowledge/distilled/11-screens-and-design-system.md#typography -->
<!-- from: knowledge/distilled/11-screens-and-design-system.md#layout -->
<!-- from: knowledge/distilled/11-screens-and-design-system.md#elevation -->

**Whether this replaces or themes `@linq/snackpaq` is unresolved** and materially affects
RF-46's 64-hour estimate, which is premised on reuse. See
[06-open-questions.md](06-open-questions.md).
<!-- from: knowledge/distilled/11-screens-and-design-system.md#design-system -->

## Defects in the mockups themselves {#mockup-defects}

Errors in the artifacts, not requirements — worth fixing before they are built to.

| Defect | Screen |
|---|---|
| A field labelled "State" whose value is the literal text "Assigned To", followed by a second "Assigned To" field — label/value mis-paired | 3 |
| The same user is "Sponsor Director" on screens 2–5 and "Sponsor Staff" on screen 6 — two distinct roles with different capabilities | 5, 6 |
| The Status filter omits **Denied**, which the cards above it display | 5 |
| Site status counts sum to 36 across a stated 24 sites, so the seven cards do not partition — but nothing says so | 5, 6 |
| Three different section counts: "7 of 10 sections", 5 table rows, 7 rail items | 3, 4 |
| Notification bell shows 5 while the sidebar badge shows 9 | 2 |
| All timestamps are May 2024 on applications for program year 2026-27 | 2, 3, 5, 6 |
| Footer reads © 2025 while the corpus is dated 2026 | 1 |
<!-- from: knowledge/distilled/11-screens-and-design-system.md#mockup-defects -->
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-3 -->

## Two screens carry a modelling error, not a cosmetic one {#modelling-errors}

- **Screen 6's Eligibility column** shows Free / Reduced / Paid as a **per-site attribute**.
  That is a per-*child* eligibility category. A site's meaningful classifications are
  Base/Non-Base, CEP participation and ISP, and severe-need qualification. If this reaches the
  schema it creates a column that cannot be populated correctly.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screens-5-6 -->
- **Screens 5 and 6 show state-side actor names** ("State Reviewer", "State Administrator") in
  the sponsor's own Updated By column. Whether a sponsor should see who at the state agency
  touched their record is a disclosure decision, not a UI detail.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screens-5-6 -->

## Iowa {#iowa}

Every screen shows Iowa or IA; screen 4 shows a Des Moines address with ZIP 50309 and a State
dropdown defaulting to Iowa. The design documents leave the demo state as "TBD," so **the
screens are currently the strongest evidence of what it is.**
<!-- from: knowledge/distilled/11-screens-and-design-system.md#demo-state -->

Two Iowa-specific details are baked into the mockups and should be configuration rather than
constants: the Congressional District dropdown offers Districts 1–4 (Iowa has four), and the
State dropdown offers only four states.
<!-- from: knowledge/distilled/11-screens-and-design-system.md#screen-4 -->

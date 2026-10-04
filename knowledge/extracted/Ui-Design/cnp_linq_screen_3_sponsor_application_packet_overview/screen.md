# Screen: cnp_linq_screen_3_sponsor_application_packet_overview

<!-- image: screen.png · 1600x1280 · RGB -->
<!-- status: described -->
<!-- described-by: model, from the rendered PNG and the paired code.html -->

## Purpose

The hub for one application. Shows completeness, blocks submission until it is ready, and
routes the sponsor into each part of the packet. This is the screen that turns "an application"
into "a packet of forms, sites and documents."

## Layout

Same shell as the dashboard (navy sidebar, top context bar), with **Applications** active in
the sidebar. A back link, "‹ Back to Applications", sits above the page title.

A **sticky footer action bar** spans the content area: **Go to Dashboard** (ghost) ·
**Validate Application** (outline, with a check icon) · **Submit for Approval** (primary).

## Content

### Header
"**Application #APP-10234**" with an **IN PROGRESS** chip. Context line: "ABC School District •
FEIN: 12-3456789 • Iowa". Metadata line: "Created: May 25, 2024 | Last Updated: May 30, 2024
10:32 AM by John Smith".

Right-hand callout box: **NEXT ACTION** — "Complete required forms and resolve validation
errors."

### Four summary cards

| Card | Value | Sub-detail | Link |
|---|---|---|---|
| Overall Progress | **68%** | green progress bar; "7 of 10 sections complete" | — |
| Validation Status | ⚠ **3 Errors** | — | View Validation |
| Site Applications | **24** | "17 Ready \| 4 Attention" | Manage Sites |
| Supporting Documents | **6** of 7 | "1 Missing" in amber | Manage Documents |

### Packet Forms
Table: **Form / Section · Status · Completion · Last Updated · Action**. Status is a chip;
completion is a percentage with a coloured bar.

| Form / Section | Status | % | Action |
|---|---|---|---|
| Sponsor Application | Complete (green) | 100% | View |
| Site Applications | In Progress (amber) | 75% | Open |
| Supporting Documents | In Progress (amber) | 85% | Open |
| Certifications & Assurances | Not Started (grey) | 0% | Start |
| Additional Information | Not Started (grey) | 0% | Start |

Expander at the base: "View form details ⌄".

### Application Details (right panel)
Label/value pairs: Program **NSLP** · Program Year **2026-27** · Application ID **APP-10234** ·
Status **In Progress** · Version **1** · State *(see open questions)* · Assigned To **—**.

### Site Applications Summary
A strip of coloured chips beginning below the fold: Total Sites · Ready · Attention · Under
Review · Returned · Approved · Denied.

## Fields

Read-only throughout. The only inputs are the two global context selectors in the top bar.

## Actions

| Control | Type | Leads to |
|---|---|---|
| Validate Application | Secondary | Runs validation; populates the Validation Status card |
| Submit for Approval | Primary | The submit transition — must be blocked while errors remain and required documents are missing |
| View Validation | Link | A validation-results view (not in this handover) |
| Manage Sites | Link | Screen 5 |
| Manage Documents | Link | A document management view (not in this handover) |
| View / Open / Start (per form row) | Row action | The corresponding form — "Sponsor Application → View" reaches screen 4 |
| Go to Dashboard | Ghost | Screen 2 |
| ‹ Back to Applications | Link | The application list |

## States

Rendered: the mid-progress state with errors outstanding.

Not designed, and each one matters:

- **Submit-ready** — 100%, zero errors, all documents attached. Does "Submit for Approval"
  change appearance, or is it always enabled and the block happens server-side? The
  requirement is that submission is blocked with a clear specific reason, which implies either
  a disabled state with an explanation or an on-click error.
- **Submitted / Under Review** — the packet becomes read-only and the footer actions must
  change. Nothing shows what a sponsor sees once the application has left their hands.
- **Returned for correction** — the state the dashboard's most prominent notification points
  at. There is no design for how the caseworker's required explanation is surfaced here.
- Approved, Denied, Withdrawn, Closed.
- Loading and error.

## Navigation

- **Reaches this screen:** Open from the dashboard attention table; the application list;
  "View Packet Overview" from screen 4; "Return to Packet Overview" from screen 5.
- **This screen reaches:** screen 4 (Sponsor Application), screen 5 (Manage Sites), the
  documents view, the validation view, the dashboard.

## Open questions

- **Three different section counts on two screens.** This card says "7 of 10 sections
  complete"; the Packet Forms table lists 5 rows; screen 4's rail lists 7 sections. Which is
  the unit of "section"?
- **A rendering defect in Application Details:** a field labelled "State" whose value is the
  literal text "Assigned To", followed by a second "Assigned To" field showing an em-dash. The
  label and value have been mis-paired.
- **What is "State" meant to be here?** Iowa is already in the context line, so this is more
  likely workflow state — in which case it duplicates the Status field two rows above.
- **Version 1** implies application versioning across resubmissions. Nothing in the
  requirements describes a version model.
- The Site Applications and Supporting Documents cards are the two that most exceed the stated
  Phase 1 scope. See `99-contradictions-and-open-questions.md#site-applications` and `#documents`.

Source: `screen.png`, cross-read with `code.html`

# Screen: cnp_linq_screen_5_site_applications_summary

<!-- image: screen.png · 1600x1280 · RGB -->
<!-- status: described -->
<!-- described-by: model, from the rendered PNG and the paired code.html -->

## Purpose

A read-oriented summary of every site application attached to one sponsor application. It sits
between the packet overview and the working site list — the sponsor comes here to see the shape
of the problem before going to screen 6 to fix it.

## Layout

Standard shell, **Applications** active. Back link "‹ Back to Application Overview". A primary
action **"Manage Site Applications"** sits top-right of the header.

## Content

### Header
"**Site Applications Summary**" with an **IN PROGRESS** chip. Context line: "Application
#APP-10234 • ABC School District • FEIN: 12-3456789 • Iowa". Explanatory sentence: "This
section provides a summary of all site applications included in this application."

### Seven status cards
Each with a tinted icon, a large count, the label, and a "View …" link.

| Card | Count | Link |
|---|---|---|
| Total Sites | 24 | View all sites → |
| Ready | 17 | View ready → |
| Attention | 4 | View attention → |
| Under Review | 3 | View under review → |
| Returned | 2 | View returned → |
| Approved | 10 | View approved → |
| Denied | 0 | View denied → |

### Filter bar
Search box ("Search sites by name or ID…"), **Status: All** dropdown, **Site: All** dropdown,
a **Filters** button, and an **Export** button with a download icon.

### Site Applications table
Header chip "24 sites". Columns: **Site ID · Site Name · Site Type · Status · Last Updated ·
Updated By · Action**.

| Site ID | Site Name | Type | Status | Last Updated | Updated By | Action |
|---|---|---|---|---|---|---|
| 00123 | Lincoln Elementary School | Base | Ready | May 30, 2024 10:15 AM | John Smith | View ⌄ |
| 00124 | Washington Middle School | Base | Returned | May 30, 2024 9:42 AM | Jane Doe | View ⌄ |
| 00125 | Roosevelt Elementary School | Non-Base | Attention | May 29, 2024 3:20 PM | John Smith | Open ⌄ |
| 00126 | Jefferson High School | Base | Under Review | May 29, 2024 11:05 AM | State Reviewer | View ⌄ |
| 00127 | Franklin Elementary School | Non-Base | Approved | May 28, 2024 4:30 PM | State Administrator | View ⌄ |
| 00128 | Madison Elementary School | Base | Ready | May 28, 2024 2:15 PM | John Smith | View ⌄ |

Pagination: "Showing 1 to 10 of 24 sites", page numbers 1 · 2 · 3 with prev/next chevrons, and
a "10 / page" selector.

Below the table (partly below the fold): a **Next Steps** panel, a **Validation Summary** panel
with a "View validation results →" link, and footer actions **Continue to Next Section** and
**Return to Packet Overview**.

## Fields

Read-only, plus four filter inputs: a free-text search, a Status select (All / Ready /
Attention / Under Review / Returned / Approved), a Site select (All / Base / Non-Base), and an
additional Filters control.

## Actions

| Control | Leads to |
|---|---|
| Manage Site Applications | Screen 6 |
| Any card "View …" link | Screen 6, pre-filtered to that status |
| View / Open (row action, with a caret) | The individual site application; the caret implies a menu of further actions, none specified |
| Export | A file download — format unspecified |
| Continue to Next Section | The next packet section (Supporting Documents, per screen 3's ordering) |
| Return to Packet Overview | Screen 3 |
| ‹ Back to Application Overview | Screen 3 |

## States

Rendered: 24 sites in mixed statuses.

Not designed:

- **Empty state** — a sponsor with no sites yet. Since screen 6 offers "Import Sites" and "Add
  Site Application", the zero-site state is the natural starting point and has no design.
- Single-site and very-large-portfolio states. A district with 200 sites gets the same layout;
  pagination handles it, but the seven summary cards and the "Attention" workflow do not
  obviously scale.
- Loading, error, and the read-only state once the parent application is submitted.

## Navigation

- **Reaches this screen:** "Manage Sites" on screen 3; the Site Applications row action on
  screen 3's Packet Forms table.
- **This screen reaches:** screen 6; individual site applications; the validation results view;
  screen 3.

## Open questions

- **The row action caret implies a menu that is never specified.** "View ⌄" is not just a link.
- **The Status filter omits Denied**, which the cards above it display as a status with a count
  of 0. A filter that cannot select a status the same screen displays is a defect.
- **The counts do not reconcile to 24.** Ready 17 + Attention 4 + Under Review 3 + Returned 2 +
  Approved 10 = 36 across a stated 24 sites, so the statuses are not mutually exclusive — most
  likely "Ready" and "Attention" are readiness flags layered over the workflow status. Nothing
  says so, and a sponsor reading seven cards will assume they partition.
- **State-side actors appear in the sponsor's own view.** "State Reviewer" and "State
  Administrator" show in the Updated By column. Whether a sponsor should see who at the state
  agency touched their record is a disclosure decision, not a UI detail.
- **Base / Non-Base is Provision 2/3 vocabulary** — base year versus non-base year — which
  implies the demo data assumes Provision schools. That is a meaningful modelling assumption to
  surface, since Provision schools drive the FA2/FA3 fiscal-action variants.
- The whole site-application concept exceeds the documented Phase 1 scope. See
  `99-contradictions-and-open-questions.md#site-applications`.

Source: `screen.png`, cross-read with `code.html`

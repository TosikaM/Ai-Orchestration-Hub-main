# Screen: cnp_linq_screen_6_site_application_list

<!-- image: screen.png · 1600x1280 · RGB -->
<!-- status: described -->
<!-- described-by: model, from the rendered PNG and the paired code.html -->

## Purpose

The working list. Where screen 5 summarises, this one lets the sponsor add, import, filter,
sort, bulk-select and act on site applications. It is the most functionally dense screen in the
handover.

## Layout

Standard shell, **Applications** active. Back link "‹ Back to Site Applications Summary". Two
header actions: **"⇧ Import Sites"** (outline) and **"+ Add Site Application"** (primary).

The top bar's Program and Program Year render as chips here (NSLP, 2026-27) rather than the
dropdowns used on screens 2–5.

## Content

### Header
"**Site Application List**" with an **IN PROGRESS** chip. Context line: "Application #APP-10234
• ABC School District • FEIN: 12-3456789 • Iowa". Instruction: "Use this list to review and
manage all site applications included in this application."

### Seven status cards
Identical values to screen 5: Total Sites 24 · Ready 17 · Attention 4 · Under Review 3 ·
Returned 2 · Approved 10 · Denied 0. Card labels are colour-coded to match their status.

### Filter bar
Search ("Search by site name, ID, or type…"), then **three** dropdowns — **Status: All**,
**Site Type: All**, **Eligibility: All** — plus a **Filters** button and a **Clear all** link.

### Table
A "Site Applications · 24 sites" header with **Export** and a **column-settings gear** on the
right.

Columns: **[select-all checkbox] · Site ID ⇅ · Site Name ⇅ · Site Type · Eligibility · Status ·
Last Updated ⇅ · Updated By ⇅ · Action**. Site names render as blue links. Four columns are
sortable.

| ☐ | Site ID | Site Name | Type | Eligibility | Status | Last Updated | Updated By | Action |
|---|---|---|---|---|---|---|---|---|
| ☐ | 00123 | Lincoln Elementary School | Base | Free | Ready | May 30, 2024 10:15 AM | John Smith | View ⌄ |
| ☐ | 00124 | Washington Middle School | Base | Reduced | Returned | May 30, 2024 9:42 AM | Jane Doe | View ⌄ |
| ☐ | 00125 | Roosevelt Elementary School | Non-Base | Free | Attention | May 29, 2024 3:20 PM | John Smith | Open ⌄ |
| ☐ | 00126 | Jefferson High School | Base | Paid | Under Review | May 29, 2024 11:05 AM | State Reviewer | View ⌄ |
| ☐ | 00127 | Franklin Elementary School | Non-Base | Free | Approved | May 28, 2024 4:30 PM | State Administrator | View ⌄ |
| ☐ | 00128 | Madison Elementary School | Base | Free | Ready | May 28, 2024 2:15 PM | John Smith | View ⌄ |
| ☐ | 00129 | Lincoln High School | Base | Reduced | Ready | May 28, 2024 1:05 PM | John Smith | View ⌄ |

Pagination with a disabled previous chevron on page 1, pages 1 · 2 · 3, and a 10/25/50 per-page
selector.

Right-hand panels (below the fold): **Need Help?**, **Quick Actions**, and a **Legend** — the
legend being the only place in the handover that promises to explain what the statuses mean.
Links to "View Validation Results →" and "Go to Supporting Documents →".

## Fields

Read-only display plus: free-text search, three filter selects, per-row selection checkboxes, a
select-all checkbox, four sortable column headers, a per-page selector, and a column-settings
control.

## Actions

| Control | Leads to |
|---|---|
| Import Sites | A bulk import flow — file format, validation, error handling all unspecified |
| Add Site Application | A new site application form — not in this handover |
| Site name (link) | The individual site application |
| View / Open ⌄ | The site application, plus an unspecified action menu |
| Row checkboxes + select-all | A bulk operation — **no bulk action bar is rendered**, so what becomes possible once rows are selected is undefined |
| Column gear | Column show/hide or reorder |
| Export | File download, format unspecified |
| Clear all | Reset filters |
| Go to Supporting Documents → | The documents section |

## States

Rendered: 24 sites, page 1, no filters applied, nothing selected.

Not designed:

- **Selected state.** Checkboxes exist with no visible bulk-action affordance. Selecting rows
  must do something.
- **Empty state** — no sites yet, which is where "Import Sites" and "Add Site Application" are
  most needed.
- **Filtered-to-empty** — a search or filter combination matching nothing.
- **Import in progress / import failed** — a bulk import of school sites will partially fail
  routinely, and there is no design for reporting which rows failed and why.
- Loading, error, and the read-only state after the parent application is submitted.

## Navigation

- **Reaches this screen:** "Manage Site Applications" on screen 5; any status card link on
  screen 5.
- **This screen reaches:** individual site applications; the add and import flows; validation
  results; supporting documents; back to screen 5.

## Open questions

- **The Eligibility column is modelled wrongly.** It shows Free / Reduced / Paid as a per-site
  attribute. Free/Reduced/Paid is a per-*child* eligibility category. A site's meaningful
  classifications are Base/Non-Base, CEP participation and ISP, and severe-need qualification.
  If this reaches the schema it produces a column that cannot be populated correctly. See
  `99-contradictions-and-open-questions.md#site-eligibility`.
- **The user's role changed.** John Smith is "Sponsor Staff" here and "Sponsor Director" on
  screens 2–5. These are two distinct roles with different capabilities — Sponsor Director can
  manage sponsor user accounts and view compliance history; Sponsor Staff cannot access
  financial data. If the intent is that Sponsor Staff can add and import sites, that is a
  permissions statement worth making deliberately.
- **Bulk selection with no bulk actions** is the largest single gap on the screen.
- Program and Program Year render as static chips here but as dropdowns on every other screen.
  Is context locked once you are inside an application?
- The **Legend** panel is the only promise in the handover to define the status vocabulary, and
  its contents are below the fold and unspecified.

Source: `screen.png`, cross-read with `code.html`

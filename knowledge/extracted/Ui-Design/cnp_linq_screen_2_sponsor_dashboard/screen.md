# Screen: cnp_linq_screen_2_sponsor_dashboard

<!-- image: screen.png · 1600x1123 · RGBA -->
<!-- status: described -->
<!-- described-by: model, from the rendered PNG and the paired code.html -->

## Purpose

The sponsor's landing screen after login. Answers "where do my applications stand, and what
needs me?" at a glance, and offers the single creative action a sponsor has: start a new
application.

## Layout

Three regions.

**Left sidebar** — dark navy, persistent, 240px. Logo mark and "CNP LINQ / Child Nutrition
Programs" at top. Nav items with icons: **Dashboard** (active, highlighted royal blue),
Applications, Sites, Documents, Notifications (red badge "9"), Reports, Audit History. Pinned
at the bottom: Help, Sign Out.

**Top bar** — white. Hamburger toggle, then two global context selectors: **PROGRAM: NSLP**
and **PROGRAM YEAR: 2026-27**, both dropdowns. Right side: notification bell with a red "5"
badge, then the user chip — "ABC School District" over "Sponsor Director" with an avatar and
a caret.

**Main content** — light grey canvas.

## Content

### Header
"**Welcome back, John Smith!**" over the context line "ABC School District • FEIN: 12-3456789
• IA". Primary action top-right: **"+ Start New Application"**.

### Application Overview
Eight metric cards, two rows of four. Each: a tinted status icon top-left, the count in large
bold top-right, the status label, and a "View all →" link.

| Status | Count | Icon tint |
|---|---|---|
| Draft | 2 | purple |
| Ready to Submit | 1 | teal |
| Under Review | 3 | blue |
| Returned | 1 | amber |
| Approved | 8 | green |
| Denied | 0 | red |
| Withdrawn | 0 | slate |
| Closed | 0 | dark slate |

### Applications Requiring Your Attention
A table: **Application ID · Program · Program Year · Status · Last Updated · Action**. Status
renders as a coloured chip. Three rows:

- APP-10234 · NSLP · 2026-27 · Returned · May 30, 2024 · Open
- APP-10235 · NSLP · 2026-27 · Under Review · May 29, 2024 · Open
- APP-10230 · NSLP · 2026-27 · Ready to Submit · May 28, 2024 · Open

Footer link: "View all applications →".

### Recent Notifications
A right-hand panel with a "View all" link and an icon-led feed:

- ↻ "Application APP-10234 was returned for correction by **Jane Doe**." — May 30, 2024 10:15 AM
- ⓘ "Supporting document required for Application APP-10230." — May 29, 2024 02:30 PM
- ✓ "Application APP-10225 was approved." — May 28, 2024 11:45 AM

## Fields

Read-only display. Two inputs, both context selectors: Program (NSLP / SBP / SFSP / CACFP) and
Program Year (2026-27 / 2025-26 / 2024-25).

## Actions

| Control | Leads to |
|---|---|
| + Start New Application | A new application in Draft — presumably screen 3 or 4 |
| Any status card "View all →" | The application list, filtered to that status |
| Open (per row) | The application packet overview (screen 3) |
| View all applications → | The unfiltered application list |
| Notifications "View all" | A notifications page (not in this handover) |
| Sidebar items | Their respective sections — only Applications is evidenced by other screens |

## States

Only the populated state is rendered. Not designed here:

- **Empty state** — a brand-new sponsor with zero applications. All eight cards read 0, the
  attention table is empty, and the notification feed is empty. This is the *first* thing a new
  sponsor sees, and it is the screen that most needs an empty state.
- Loading and error states, though Sprint 5 requires all three to be handled with no console
  errors.
- What "Attention" means as a selection rule — which statuses qualify an application for the
  attention table. Returned and Ready to Submit clearly do; Under Review is less obvious, since
  the sponsor cannot act on it.

## Navigation

- **Reaches this screen:** successful login as a sponsor role; the "Go to Dashboard" action on
  screen 3; the Dashboard nav item.
- **This screen reaches:** the application packet overview (screen 3) via Open; the filtered
  application list via any card; a new application via Start New Application.

## Open questions

- All timestamps are **May 2024** on applications for program year **2026-27** — an application
  for a school year two years away, last touched two years ago. Mock data, but it will read as
  a defect in a demo.
- The notification bell shows **5** while the sidebar Notifications badge shows **9**. Two
  different counts for the same thing on the same screen.
- Withdrawn and Closed appear as first-class statuses here but are not in any Phase 1
  requirement.
- Program and Program Year are global selectors, but nothing on the screen indicates whether
  the metric counts are scoped by them. If they are, an eight-card overview that changes
  entirely when you switch program needs that made obvious.

Source: `screen.png`, cross-read with `code.html`

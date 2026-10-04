# Screens and design system

Six screens were delivered as paired HTML mockups and PNG renders, plus a design-system
specification. The screens are **sponsor-facing only** — no state-side caseworker, reviewer or
config-admin screens are in this handover.
<!-- source: Ui-Design/cnp_linq_screen_1_login_sso/code.md#screen -->
<!-- source: Ui-Design/cnp_linq_screen_6_site_application_list/code.md#screen -->

## The demo state is Iowa {#demo-state}

Every screen carries "Iowa" or "IA" in the sponsor context line. Screen 4 shows a Des Moines,
Iowa address with ZIP 50309, and the State dropdown offers Iowa, Illinois, Nebraska and
Minnesota with Iowa selected. The design documents elsewhere leave the demo state as "TBD."
<!-- source: Ui-Design/cnp_linq_screen_2_sponsor_dashboard/screen.md#screen -->
<!-- source: Ui-Design/cnp_linq_screen_4_sponsor_application/screen.md#screen -->
<!-- source: Ui-Design/cnp_linq_screen_4_sponsor_application/code.md#visible-text -->

Iowa is corroborated by the presence of a dedicated legacy analysis of the Iowa CTS
application-to-approval workflow, and by Iowa appearing as the worked configuration example in
the journey document.
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#feature-overview -->
<!-- source: Application-to-Approval-Journey.md#config-example -->

## The shared shell {#shell}

A persistent dark-navy sidebar with eight items — **Dashboard, Applications, Sites, Documents,
Notifications (badged), Reports, Audit History, Help, Sign Out** — and a top utility bar
carrying a **Program selector** (NSLP / SBP / SFSP / CACFP), a **Program Year selector**
(2026-27 / 2025-26 / 2024-25), a notification bell with a count badge, and a user/role chip
showing the organization and role.
<!-- source: Ui-Design/cnp_linq_screen_2_sponsor_dashboard/code.md#navigation -->
<!-- source: Ui-Design/cnp_linq_screen_2_sponsor_dashboard/screen.md#screen -->

Program and program year as **global context selectors** in the shell rather than per-page
filters is a significant structural decision: it matches the URL scheme in the frontend
architecture, where program year is a path segment (`/:programYear/applications/:program/
:formType`) precisely so concurrent tabs across different program years do not conflict.
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-3 -->

The sponsor context line — organization name · FEIN · state — repeats on every screen.
<!-- source: Ui-Design/cnp_linq_screen_3_sponsor_application_packet_overview/code.md#visible-text -->

## Screen 1 — Login (SSO) {#screen-1}

A single centred card: the CNP LINQ mark, "Sign in with your organization account," and one
button, **Sign in with SSO**. Below it: "Having trouble signing in? Contact your systems
administrator." Footer links to Privacy Policy, Terms of Use and Support.

**There is no username or password field on this screen** — which is the correct rendering of
the requirement that authentication happens at a real identity provider and there is no
fallback path.
<!-- source: Ui-Design/cnp_linq_screen_1_login_sso/screen.md#screen -->
<!-- source: Ui-Design/cnp_linq_screen_1_login_sso/code.md#interactive-controls -->
<!-- source: 01_FRD_Identity_Access.md#section-4 -->

## Screen 2 — Sponsor dashboard {#screen-2}

"Welcome back, John Smith!" over the sponsor context line, with a primary **Start New
Application** action top-right.

**Application Overview** — eight metric cards in two rows of four, each with an icon, a count
and a "View all →" link: Draft (2) · Ready to Submit (1) · Under Review (3) · Returned (1) ·
Approved (8) · Denied (0) · Withdrawn (0) · Closed (0).

**Applications Requiring Your Attention** — a table of Application ID, Program, Program Year,
Status, Last Updated, Action (Open).

**Recent Notifications** — an icon-led feed: "Application APP-10234 was returned for correction
by Jane Doe," "Supporting document required for APP-10230," "APP-10225 was approved."
<!-- source: Ui-Design/cnp_linq_screen_2_sponsor_dashboard/screen.md#screen -->
<!-- source: Ui-Design/cnp_linq_screen_2_sponsor_dashboard/code.md#visible-text -->

## Screen 3 — Application packet overview {#screen-3}

The hub for one application. Header: "Application #APP-10234" with an **IN PROGRESS** chip,
created/last-updated attribution, and a **Next Action** callout ("Complete required forms and
resolve validation errors").

Four summary cards: **Overall Progress** (68%, "7 of 10 sections complete", with a progress
bar) · **Validation Status** (3 Errors, "View Validation") · **Site Applications** (24, "17
Ready | 4 Attention", "Manage Sites") · **Supporting Documents** (6 of 7, "1 Missing", "Manage
Documents").

**Packet Forms** table — Form/Section, Status, Completion %, Last Updated, Action:
Sponsor Application (Complete, 100%, View) · Site Applications (In Progress, 75%, Open) ·
Supporting Documents (In Progress, 85%, Open) · Certifications & Assurances (Not Started, 0%,
Start) · Additional Information (Not Started, 0%, Start).

**Site Applications Summary** strip and an **Application Details** panel (Program, Program Year,
Application ID, Status, Version, Assigned To).

Footer action bar, always visible: **Go to Dashboard** · **Validate Application** · **Submit for
Approval**.
<!-- source: Ui-Design/cnp_linq_screen_3_sponsor_application_packet_overview/screen.md#screen -->
<!-- source: Ui-Design/cnp_linq_screen_3_sponsor_application_packet_overview/code.md#visible-text -->

The **explicit Validate action separate from Submit** matches the requirement that submission
requires completeness and the system identifies what is missing *before* submission is allowed.
<!-- source: 03_FRD_Application_Submission.md#section-3 -->

## Screen 4 — Sponsor application form {#screen-4}

A left rail of **seven numbered sections** with per-section status: 1 Organization Information
(In Progress) · 2 Contact Information · 3 Program Information · 4 Eligibility ·
5 Certifications & Assurances · 6 Additional Information · 7 Review & Submit (all Not Started).

Section 1 field inventory:

| Group | Field | Type | Required |
|---|---|---|---|
| Organization Details | Sponsor / Agency Type | select — School District, Private Non-Profit, Charter School, Government Agency | Yes |
| | Organization Name | text | Yes |
| | FEIN | text | Yes |
| | DUNS / UEI Number | text (with info tooltip) | No |
| | Congressional District | select — District 1–4 | No |
| | Operational Start Date | date | Yes |
| | Operational End Date | date | Yes |
| | Fiscal Year Start Month | select — July, January, October | Yes |
| Primary Address | Street Address | text | Yes |
| | Address Line 2 | text, placeholder "(Optional)" | No |
| | City | text | Yes |
| | State | select | Yes |
| | ZIP Code | text | Yes |
<!-- source: Ui-Design/cnp_linq_screen_4_sponsor_application/code.md#interactive-controls -->
<!-- source: Ui-Design/cnp_linq_screen_4_sponsor_application/screen.md#screen -->

The sample data is internally consistent with the July–June NSLP program year: operational
dates 07/01/2026 – 06/30/2027, fiscal year start July, program year 2026-27.
<!-- source: Ui-Design/cnp_linq_screen_4_sponsor_application/screen.md#screen -->
<!-- source: CSN-Data-140826-132933.md#page-8 -->

The **Fiscal Year Start Month** options — July, January, October — map exactly to the three
program-year cycles (NSLP/SBP July, SFSP January, CACFP October).
<!-- source: Ui-Design/cnp_linq_screen_4_sponsor_application/code.md#visible-text -->
<!-- source: CSN-Data-140826-132933.md#page-8 -->

Two behaviours visible in the chrome: an **"Autosaved: 2 min ago"** indicator with a tick, and
three footer actions **Cancel · Save Draft · Save & Continue** — matching the requirement that
in-progress work is saved and resumable. A **Validate** action sits in the page header too.
<!-- source: Ui-Design/cnp_linq_screen_4_sponsor_application/screen.md#screen -->
<!-- source: 03_FRD_Application_Submission.md#section-3 -->

Required fields are marked with a red asterisk and the legend "* Indicates required field."
<!-- source: Ui-Design/cnp_linq_screen_4_sponsor_application/screen.md#screen -->

## Screens 5 and 6 — Site applications {#screens-5-6}

Screen 5 is a **summary**; screen 6 is the **working list**. Both carry the same seven status
cards: Total Sites (24) · Ready (17) · Attention (4) · Under Review (3) · Returned (2) ·
Approved (10) · Denied (0).

Screen 5 offers Search, a Status filter, a Site filter (All / Base / Non-Base), Filters and
Export, over a table of Site ID, Site Name, Site Type, Status, Last Updated, Updated By,
Action. Footer actions: **Continue to Next Section** and **Return to Packet Overview**.

Screen 6 adds **Import Sites** and **Add Site Application** actions, row checkboxes for bulk
selection, sortable columns, a third **Eligibility** filter and column, a Clear-all control, a
column-settings gear, and pagination (10/25/50 per page).
<!-- source: Ui-Design/cnp_linq_screen_5_site_applications_summary/screen.md#screen -->
<!-- source: Ui-Design/cnp_linq_screen_6_site_application_list/screen.md#screen -->
<!-- source: Ui-Design/cnp_linq_screen_6_site_application_list/code.md#interactive-controls -->

Sample rows show state-side actors appearing in the sponsor's own view — "State Reviewer" and
"State Administrator" in the *Updated By* column — so the sponsor sees who acted on their site
applications.
<!-- source: Ui-Design/cnp_linq_screen_6_site_application_list/screen.md#screen -->

> The screens require a **site-application sub-lifecycle** that the Phase 1 requirements do not
> describe. See `99-contradictions-and-open-questions.md#site-applications`.

> Screen 6 models **Eligibility (Free / Reduced / Paid) as a per-site attribute**, which
> conflicts with the domain model. See
> `99-contradictions-and-open-questions.md#site-eligibility`.

## The status vocabulary in the UI {#status-vocabulary}

Eight application-level statuses appear consistently across the dashboard and the design
system: **Draft · Ready to Submit · Under Review · Returned (for Correction) · Approved ·
Denied · Withdrawn · Closed.** Plus **In Progress** as a packet-level status and **Attention**
as a site-level one.
<!-- source: Ui-Design/cnp_linq_screen_2_sponsor_dashboard/code.md#headings -->
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#semantic-status-lifecycle -->

Note the UI uses **Denied**, matching the FRDs and the feature list, rather than the
prototype plan's **Declined**.
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#semantic-status-lifecycle -->
<!-- source: 51 Feature List.md#RF-15 -->
<!-- source: CSN-Prototype-140826-133159.md#page-8 -->

## The design system — "Public Trust Modern" {#design-system}

An authoritative, accessible public-sector aesthetic for state agencies, sponsors, caseworkers
and regulatory auditors. Three tenets: **institutional trust and rigor** (deep navy structural
anchors), **flawless accessibility (WCAG 2.1 AA)**, and **operational clarity** (disciplined
hierarchy for dense regulatory workflows). Colour is used strictly for semantic communication
— status progression and action priority — rather than ornament.
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#brand-style -->

### Colour {#colours}

- **Primary Navy `#0B2A56`** — sidebar, headers, active nav, branding
- **Secondary Royal Blue `#0D52B7`** — action buttons, focus outlines, links
- **Tertiary Dark Royal `#185ADB`** — hover states
- **Neutrals `#64748B` `#334155` `#F4F6F9` `#E2E8F0`** — canvas is `#F4F6F9`, elevated content
  is pure `#FFFFFF`
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#colors -->

**Status pairings are strict**, each a text colour on a tint with a border:

| Status | Text | Tint | Border |
|---|---|---|---|
| Draft | `#7C3AED` | `#F5F3FF` | `#DDD6FE` |
| Ready to Submit | `#0D9488` | `#F0FDFA` | `#99F6E0` |
| Under Review | `#2563EB` | `#EFF6FF` | `#BFDBFE` |
| Returned for Correction | `#D97706` | `#FFFBEB` | `#FDE68A` |
| Approved | `#16A34A` | `#F0FDF4` | `#BBF7D0` |
| Denied | `#DC2626` | `#FEF2F2` | `#FECACA` |
| Withdrawn | `#64748B` | `#F1F5F9` | `#CBD5E1` |
| Closed | `#334155` | `#E2E8F0` | `#94A3B8` |
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#semantic-status-lifecycle -->

### Typography {#typography}

**Public Sans** for headlines (chosen for sturdy institutional geometry and public-sector
legibility standards) and **Source Sans 3** for body and labels (tall x-height and open
counters keep glyphs distinct at 11–12px in dense tables and status badges).

All numeric figures in data summaries use `font-variant-numeric: tabular-nums` to preserve
column alignment and rapid vertical scanning.
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#typography -->

### Layout {#layout}

A 12-column grid with three breakpoints:

| Breakpoint | Sidebar | Grid | Gutters | Status cards |
|---|---|---|---|---|
| Desktop ≥1440px | Permanent, 240px | 12-column | 24px, 32px page padding | 3 columns each, 4 across |
| Tablet 768–1439px | Collapsed icon rail, 64px | 8-column | 16px, 24px margins | 2 or 4 across |
| Mobile <768px | Off-canvas drawer, hamburger | 4-column | 12px margins | 2-column; **dense tables convert to vertical stacked data cards** |

Strict 4px/8px baseline scale. Interactive components hold a minimum 40px target height, 44px
on touch viewports.
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#layout-spacing -->

### Elevation and focus {#elevation}

Five levels, favouring **boundary clarity over cinematic drop shadows** — an explicit
accessibility choice for well-lit office environments. Cards sit on white with a 1px `#E2E8F0`
border and a `0 1px 3px rgba(11,42,86,0.05)` micro-shadow; modals use
`0 16px 36px rgba(11,42,86,0.20)` over a navy scrim with 2px backdrop blur.

Every focused interactive element gets a **dual focus ring**:
`box-shadow: 0 0 0 2px #FFFFFF, 0 0 0 4px #0D52B7` — so focus stays visible against any
background.
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#elevation-depth -->

### Shape and components {#components}

Soft geometry: 4px radius on inputs, table cells, compact buttons, tabs and status badges; 8px
on cards, modals and dashboard widgets; full radius **only** on notification pips and avatars.

- **Buttons** — Primary `#0D52B7`/white; Secondary outline; Tertiary ghost; Destructive
  `#DC2626`. Heights 36px standard, 32px compact for table actions, 44px touch.
- **Status badges** — `[Icon] + Label`, Source Sans 3 12px semibold, 2px 8px padding.
- **Form inputs** — 38px height, `#CBD5E1` border resting, `#0D52B7` border plus a 3px focus
  ring, red border with helper text and alert icon on error.
- **Metric cards** — tinted icon top-left, status label top-right, Public Sans 28px bold metric,
  "View all →" link at the base. *(This is exactly what screens 2, 3, 5 and 6 render.)*
- **Data tables** — `#F8FAFC` header with 12px uppercase semibold labels, 2px bottom border,
  12px/16px cell padding, alternating hover.
- **Sidebar** — navy, active item in royal blue with a 3px `#38BDF8` left accent.
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#shapes -->
<!-- source: Ui-Design/public_trust_modern/DESIGN.md#components -->

> The design system specifies Public Sans / Source Sans 3 and its own component library, while
> the feature list and prototype plan mandate `@linq/snackpaq`. See
> `99-contradictions-and-open-questions.md#design-system`.

## Mockup defects worth noting before build {#mockup-defects}

These are errors in the mockups themselves, not requirements:

- Screen 3's Application Details panel renders a field labelled **"State"** whose value is the
  literal text "Assigned To", followed by a second "Assigned To" field with an em-dash. A
  duplicated-label rendering bug.
<!-- source: Ui-Design/cnp_linq_screen_3_sponsor_application_packet_overview/screen.md#screen -->
- The same user, John Smith, is labelled **Sponsor Director** on screens 2–5 and **Sponsor
  Staff** on screen 6. These are two distinct roles with different capabilities.
<!-- source: Ui-Design/cnp_linq_screen_5_site_applications_summary/screen.md#screen -->
<!-- source: Ui-Design/cnp_linq_screen_6_site_application_list/screen.md#screen -->
<!-- source: CSN-CNP Rights-140826-132801.md#page-7 -->
- Screen 5's Status filter omits **Denied**, which the summary cards above it display.
<!-- source: Ui-Design/cnp_linq_screen_5_site_applications_summary/code.md#interactive-controls -->
- All sample timestamps are **May 2024** while the program year is **2026-27** — an application
  for a school year two years in the future, last updated two years in the past.
<!-- source: Ui-Design/cnp_linq_screen_2_sponsor_dashboard/screen.md#screen -->
- The login footer reads **© 2025** while the rest of the corpus is dated 2026.
<!-- source: Ui-Design/cnp_linq_screen_1_login_sso/screen.md#screen -->
- Screen 3's Overall Progress says "7 of 10 sections complete" while the Packet Forms table
  lists five rows and screen 4's rail lists seven sections. Three different section counts.
<!-- source: Ui-Design/cnp_linq_screen_3_sponsor_application_packet_overview/screen.md#screen -->
<!-- source: Ui-Design/cnp_linq_screen_4_sponsor_application/screen.md#screen -->

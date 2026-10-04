# Screen: cnp_linq_screen_4_sponsor_application

<!-- image: screen.png · 1600x1172 · RGBA -->
<!-- status: described -->
<!-- described-by: model, from the rendered PNG and the paired code.html -->

## Purpose

The application form itself — a seven-section wizard with a persistent section rail. This is
the screen RF-17 governs: the field set must be rendered from server-supplied metadata, not
hardcoded.

## Layout

Standard shell. Back link "‹ Back to Packet Overview". Two columns below the header: a narrow
**Application Sections** rail on the left, the active section's form on the right.

### Header
"**Sponsor Application**" with an **IN PROGRESS** chip. Context line: "Application ID:
#APP-10234 • ABC School District • FEIN: 12-3456789 • Iowa". Right side: "Autosaved: 2 min ago"
with a green tick, then **Validate** (outline) and **View Packet Overview** (primary).

### Section rail
Seven numbered items, each with a status caption. The active one is highlighted with a filled
blue numeral and a chevron.

| # | Section | Status |
|---|---|---|
| 1 | Organization Information | In Progress |
| 2 | Contact Information | Not Started |
| 3 | Program Information | Not Started |
| 4 | Eligibility | Not Started |
| 5 | Certifications & Assurances | Not Started |
| 6 | Additional Information | Not Started |
| 7 | Review & Submit | Not Started |

### Section 1 — Organization Information
Sub-heading "Please provide your organization details." with the legend "* Indicates required
field" in red on the right. Two field groups.

## Fields

**ORGANIZATION DETAILS**

| Field | Type | Required | Sample value | Options / notes |
|---|---|---|---|---|
| Sponsor / Agency Type | select | ✱ | School District | School District, Private Non-Profit, Charter School, Government Agency |
| Organization Name | text | ✱ | ABC School District | |
| FEIN | text | ✱ | 12-3456789 | Rendered with a hyphen mask |
| DUNS / UEI Number | text | — | 987654321 | Carries an ⓘ info tooltip |
| Congressional District | select | — | "Select…" (unset) | District 1–4 |
| Operational Start Date | date | ✱ | 07/01/2026 | Calendar picker |
| Operational End Date | date | ✱ | 06/30/2027 | Calendar picker |
| Fiscal Year Start Month | select | ✱ | July | July, January, October |

**PRIMARY ADDRESS**

| Field | Type | Required | Sample value | Options / notes |
|---|---|---|---|---|
| Street Address | text | ✱ | 123 Main Street | |
| Address Line 2 | text | — | placeholder "(Optional)" | |
| City | text | ✱ | Des Moines | |
| State | select | ✱ | Iowa | Iowa, Illinois, Nebraska, Minnesota |
| ZIP Code | text | ✱ | 50309 | |

Two details in the sample data are internally consistent and worth preserving: the operational
dates 07/01/2026–06/30/2027 match the NSLP July–June program year for PY 2026-27, and the three
Fiscal Year Start Month options map exactly to the three program-year cycles (NSLP/SBP July,
SFSP January, CACFP October).

## Actions

| Control | Type | Behaviour |
|---|---|---|
| Cancel | Ghost | Discard — no confirmation dialog is designed |
| Save Draft | Outline, with save icon | Persist without advancing |
| Save & Continue → | Primary | Persist and advance to section 2 |
| Validate | Header outline | Run validation on the current state |
| View Packet Overview | Header primary | Screen 3 |
| Any rail item | Nav | Jump to that section |
| ‹ Back to Packet Overview | Link | Screen 3 |

Autosave is implied by the "Autosaved: 2 min ago" indicator, which sits alongside an explicit
Save Draft button — so both an automatic and a manual save path exist.

## States

Rendered: section 1 in progress, all fields populated and valid.

Not designed:

- **Field-level validation errors.** The design system specifies an error treatment (red border,
  helper text, alert icon) but no screen shows one, and this is the screen where the
  requirement "the specific failure is recorded and shown to the sponsor" lands.
- **Read-only fields.** Iowa's documented configuration sources addresses from the state EIS
  and renders them read-only. That is exactly these five address fields, and there is no
  rendering of it — no lock icon, no "managed by your state agency" explanation.
- **Conditional fields appearing and disappearing.** The frontend architecture describes live
  `hideExpression` evaluation; nothing here shows it.
- Section-complete state (what section 1 looks like at 100%), and the Review & Submit section.
- Loading, saving-in-flight, and save-failed.

## Navigation

- **Reaches this screen:** "View" on the Sponsor Application row of screen 3.
- **This screen reaches:** sections 2–7 via the rail or Save & Continue; screen 3 via either
  header or back link.

## Open questions

- **Sections 2–7 have no field inventory anywhere in this handover.** Only section 1 is
  designed. Contact Information, Program Information, Eligibility, Certifications & Assurances,
  Additional Information and Review & Submit are named and otherwise unspecified — and RF-17
  requires the whole form to be server-defined metadata, so the metadata for six of seven
  sections does not exist.
- **The State dropdown offers four states** (Iowa, Illinois, Nebraska, Minnesota) for a
  sponsor's mailing address. A sponsor in a single-tenant Iowa deployment could plausibly have
  an out-of-state mailing address, but a four-item list is neither "all 50" nor "Iowa only" —
  is it a mock shortcut, or a real constraint?
- **Congressional District offers District 1–4.** Iowa has four congressional districts, which
  makes this Iowa-specific data in what should be a configuration-driven form.
- The FEIN field shows a formatted value; whether the mask is enforced, and what validation
  applies, is unspecified. FRD-05 checks the sponsor's **EIN** against the NDL — this is the
  field that feeds a federal compliance gate.

Source: `screen.png`, cross-read with `code.html`

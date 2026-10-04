<!-- EXTRACTED from knowledge/inbox/CSN-Frontend Architecture-140826-133148.pdf on 2026-09-09T13:30:47Z -->
<!-- DO NOT EDIT. If extraction is wrong, fix the extractor and re-run. A
     hand-patched extraction no longer matches its source, and once that is
     true of one file no citation in this corpus can be trusted. -->


<!-- page: 1 -->
Frontend Architecture
Three Layers of Configuration
Forms are NOT built by enabling feature flags. Feature flags, form
metadata, and field-level rules are three separate layers. Confusing
them creates an unmaintainable system where every field change
requires a deployment.
1. Module Level
Feature Flags (LaunchDarkly) — Does this module exist for this tenant?
program.nslp.enabled true→ Show NSLP nav item, load NSLP routes
program.nslp.enabled false→ NSLP nav item hidden, routes 404, module code never loads
platform.training.enabled true→ Training section appears in nav (HI only in DIS; all CTS
states)
claims.auto-decline.enabled true→ Auto-decline logic active in claim submission
dircert.directver.enabled true (IN only)→ DirectVer sponsor-facing DC module shown;
Indiana reference implementation
Granularity: module / feature / business rule. Not field-level. Evaluated by Angular route guards
and component-level LD directives.
<!-- page: 2 -->
Shell Initiation: Angular App Bootstrap
2. Form Level
Form Metadata (cnp_global FormDefinition) — What sections and fields exist?
AnnualFormType: FSMC → FSMC section only appears if sponsor.hasFsmcContract = true
SiteApp section: NonCong → Non-congregate section only if program = SFSP or (NSLP +
PY ≥  2024)
ReviewVersion: 4.2 NSLP → Question bank loaded from cnp_global ReviewVersions
VCAScoringTool v3.2 → VCA checklist sections loaded from cnp_global
VCAScoringToolItems
Definitions in cnp_global (shared all states). Per-tenant overrides in cnp_ops. No deployment
needed to change form structure.
3. Field Level
Formly Field Config — Required / optional / hidden / conditional?
enrollment All states — must have enrollment for NSLPrequired
avgCostHalfPint  Required only if Special Milk Program active optional
nonCongregateDays Visible only if nonCongMode ≠  'congregate-only' conditional
stateMatchAmount  Hidden in states with no state match rate hidden
Resolved server-side per request: base schema from cnp_global + tenant override + program
context. Returned as FormlyFieldConfig[] to Angular.
Subdomain Resolution
Browser hits .
Route 53 → CloudFront →
ALB. YARP extracts "mn"
from Host header → resolves
TenantId = "mn-doe".
mn.linqcnp.com
1 Host: mn.linqcnp.com
2 → TenantId: "mn-doe"
Keycloak OIDC
Angular checks for valid
JWT in memory. If
absent, redirects to ut-
doe Keycloak realm →
state IdP
(AD/SAML/JWT) →
returns JWT with
Tenant Config Load
Angular calls GET
/api/tenant/config. API
reads from cnp_global (387
shared reference tables).
ICnpContext
simultaneously resolves
the state's cnp_ops Aurora
connection (1,015
<!-- page: 3 -->
3 → ICnpContext: GlobalDb
(cnp_global) + StateDb
(ut-doe.cnp_ops)
tenant_id, roles,
programs claims.
1 jwt.tenant_id = "mn-
doe"
2 jwt.programs =
["NSLP","CACFP"]
operational tables).
Returns: agency name,
logo S3 URL, brand color,
LD bootstrap payload,
cnp_ops connection
confirmed.
1 { agencyName:
"Minnesota DOE",
2   logoUrl: "s3://…/mn-
doe/logo.svg",
3   primaryColor:
"#1BAAC1" }
Brand Tokens Applied
CSS custom properties set
on :root. @linq/snackpaq
components automatically
pick up tenant brand. Logo
element src updated.
Agency name in nav
header.
1 :root {
2   --linq-primary:
#1BAAC1;
3   --linq-agency: "MN
DOE"
4 }
LaunchDarkly
Bootstrap
LD SDK initialized with
tenant context {tenantId,
stateCode, programs}.
Bootstrap payload (from
step 3) seeds all 47 flags
instantly — no extra
network call. (43 original +
session replay ×3 + non-
congregate SFSP)
1 ldClient.identify({
2   kind:"multi",
3   tenant:{key:"mn-doe"}
4 })
Nav + Routes Built
Angular route guards
check LD flags.
program.nslp.enabled →
NSLP routes registered.
platform.training.enabled =
false → Training route
removed. Nav items
rendered conditionally.
1 canActivate:
[FeatureFlagGuard]
2 flag:
'program.nslp.enabled'
Session Replay Active
LD Session Replay SDK
starts recording. Privacy
mode: mask-all by default.
Student PII elements have
ld-privacy-redact attribute.
<!-- page: 4 -->
Form Rendering: Form Built at Runtime
Replay linked to LD tenant
context.
1 privacySettings: {
2   defaultMode: 'mask'
3 }
User Navigates to Form
Program year is part of the
URL path: /2025-
26/applications/nslp/spons
or-app. Angular Router
segments: 
/:programYear/applica
tions/:program/:formT
ype . This allows
concurrent tabs across
different program years
without session conflict.
tenantId is resolved via
ICnpContext (subdomain),
not in the URL.
API: GET /form-schema
Angular calls GET
/api/forms/schema?
formType=NslpSponsorApp
&programYear=2026. Server
resolves schema from
cnp_global + tenant
overrides.
1 GET /api/forms/schema
2 ?formType=NslpSponsorApp
3 &programYear=2026
4 &tenantId=mn-doe
Server Builds Schema
1. Load base FormDefinition
from cnp_global. 
2. Apply tenant overrides
(cnp_ops). 
3. Apply program-year
conditions (e.g., nonCong
fields only if PY ≥ 2024).
4. Return
FormlyFieldConfig[].
Formly Renders
Angular Formly receives
FormlyFieldConfig[].
Renders inputs, selects, date
pickers, custom
components.
Required/hidden/conditional
states applied from config —
no if/else in template.
1 formly-form
2  [fields]="schema"
3  [model]="sponsorApp"
Live Conditional Logic
hideExpression and
expressions evaluate against
live form model. Changing
"Does your sponsor use
FSMC?" to Yes → FSMC
section appears instantly
without page reload.
1 hideExpression:
2  "!model.usesFsmc"
6Validation on Submit
Formly validates all visible
required fields. Hidden fields
are skipped automatically.
Custom validators
(enrollment cap, 60-day
deadline) run via
asyncValidators from API.
<!-- page: 5 -->
PDF Strategy — User-Initiated Print + Automated Snapshots
PDF Snapshot Triggered
On status change
(Submitted/Approved), SQS
event fires → Document
Service renders PDF
snapshot of the form as it
appeared at this moment.
Stored to S3.
1 event:
ApplicationSubmitted
2 → SQS → PDF render
3 → S3 snapshot
User-Initiated Print (Forms)
Browser window.print()
with print CSS (@media
print ). Navigation,
sidebars, action buttons
hidden via display:none .
No server component.
Covers: applications,
budgets, management
plans, claim summaries.
Simplest — works in all
browsers.
1 @media print {
2  .nav, .sidebar, .action-
bar { display:none; }
3  .form-content {
width:100%; }
4 }
Multi-Page Reports —
IPdfRenderService
(QuestPDF)
NA-44 federal reports,
review reports, and audit
exports use server-side
headless Chromium via 
QuestPDF in the Document
Service. API endpoint
accepts a report token →
renders → returns S3 pre-
signed URL. Covers complex
paginated documents where
print CSS is insufficient.
1 POST /api/reports/render
2 { reportType: "FNA-44",
claimId: 123 }
3 → SQS →
DocumentService.IPdfRende
rService
4 → S3 pre-signed URL (15-
min TTL)
Automated Status-Change
Snapshots (existing)
On ApplicationSubmitted /
ClaimLocked /
ReviewClosed events, SQS
triggers Document Service
→ IPdfRenderService → S3
immutable snapshot. Pre-
signed URL returned on-
demand. This path already
existed in the design — see
flow step 7 above.
<!-- page: 6 -->
FormlyFieldConfig: Field-Level Required / Optional / Hidden
EvoPdf (legacy commercial library) is not carried forward. Print CSS
covers the 90% case with zero infrastructure. QuestPDF covers the
10% of complex reports. The IPdfRenderService  interface in the
Platform Engine abstracts both — Document Service chooses the
implementation at render time based on ReportComplexity
metadata.
1 // Server returns this array for NslpSponsorApp — built from cnp_global + tenant overrides
2 const schema: FormlyFieldConfig[] = [
3 {
4 key: 'organizationName',
5 type: 'input',
6 props: {
7 label: 'Organization Name',
8 required: true,        // All states — always required
9 }
10 },
11 {
12 key: 'stateMatchAmount',
13 type: 'currency',
14 props: { label: 'State Match Amount', required: true },
15 // Hidden for states with no state match (config-driven, not hardcoded)
16 hide: false,              // true = UT (has state match), false = GA (no state match)
17 expressions: {
18 hide: '!config.stateMatchEnabled'   // resolved from tenant config
19 }
20 },
21 {
22 key: 'avgCostHalfPint',
23 type: 'currency',
24 props: {
25 label: 'Avg Cost per Half Pint',
26 required: false,       // Present but optional unless SMP enabled
27 description: 'Required only if Special Milk Program is active'
28 },
29 expressions: {
30 'props.required': 'model.programCodes?.includes("SMP")'
31 }
32 },
33 {
34 key: 'nonCongregateMealMode',
35 type: 'select',
36 props: {
37 label: 'Non-Congregate Service Mode',
38 required: false,
39 options: [
40 { label: 'Congregate Only', value: 'CONGREGATE' },
41 { label: 'Non-Congregate Only', value: 'NON_CONGREGATE' },
42 { label: 'Mixed', value: 'MIXED' }
43 ]
44 },
45 // Hidden entirely for NSLP if programYear < 2024 (federal gate)
46 expressions: {
47 hide: 'model.programYear < 2024 || !model.programCodes?.includes("SSO")'
48 }
49 },
50 {
51 key: 'boardMemberCount',
<!-- page: 7 -->
Field States
52 type: 'number',
53 props: {
54 label: 'Number of Board Members',
55 required: true,
56 min: 3,
57 description: 'CACFP requires minimum 3 board members'
58 },
59 // Only required for CACFP sponsors — present but optional for SFSP/NSLP
60 expressions: {
61 'props.required': 'model.programCodes?.includes("CACFP")'
62 }
63 }
64 ]
Required props.require
d: true
Field shown with
red asterisk (*).
Form cannot
submit if empty.
Formly adds
RequiredValidator
automatically.
Custom
validators also
run.
Organization
Name,
Agreement
Number,
Enrollment count
for NSLP sites
Optional props.require
d: false
Field shown
without asterisk.
Can be left blank.
Submits without
error.
No required
validation.
Custom
validators may
still run (e.g.,
format check if
value provided).
Average Cost per
Half Pint (shown
for all, required
only if SMP
active), Phone
extension
Hidden hide: true  or 
expressions.h
ide
Field NOT in
DOM. No label,
no input. Cannot
be tabbed to.
Value reset to null
if model changes
to hide.
Skipped entirely
— no required
check, no format
check. Safe for
fields that don't
apply.
State Match
Amount (hidden
in states with 0%
match), Non-
Congregate
mode (hidden if
PY < 2024 or not
SSO)
Read-Only props.disable
d: true  or 
Field shown,
value visible, but
cannot be edited.
Skipped for user-
facing validation.
Server still
Agreement
Number (system-
generated, shown
State Formly Config Behavior Validation Example in CNP
<!-- page: 8 -->
State-Specific Branding: Logo, Colors, Agency Name
props.readonl
y: true
Appears grayed
out.
validates on
submit.
for reference),
Approved
ClaimLaws rate
(frozen — display
only)
Conditional expressions:
{ hide,
'props.requir
ed' }
Field visibility or
required state
changes
dynamically
based on other
field values or
model state.
Required
validation
activates/deactiv
ates in real time.
Angular Formly
re-evaluates on
every model
change.
FSMC section
appears when
usesFsmc = true;
Non-cong
distribution days
appear when
mode ≠
CONGREGATE;
Board member
count required
when CACFP in
programCodes
How It Works: Tenant Config → CSS
Custom Properties
Logo assets stored in S3 under 
/{tenantId}/branding/logo.svg .
State agencies upload their own logo via a
branding settings page. Served via
CloudFront CDN with long cache-control
headers. If no logo: LINQ default logo shown.
Examples
1 // 1. Tenant config loaded at bootstrap
(GET /api/tenant/config)
2 interface TenantConfig {
3 agencyName: string;         //
"Minnesota Department of Education"
4 logoUrl: string;            // S3 pre-
signed URL or CDN URL
5 primaryColor: string;       //
"#1BAAC1" — Sky Blue for MN
6 tenantCode: string;         // "MN"
7 }
8

<!-- page: 9 -->
Form Preview
The same NslpSponsorApp  FormDefinition is loaded for all states. Utah sees State Match
(because config.stateMatchEnabled = true ). Georgia does not. Montana does not see
the SSO non-congregate fields (because Montana does not participate in SSO). No code
branches. Only metadata differences between tenants. Once again, this is only an example of
what it COULD look like, not a design requirement.
9 // 2. Applied to :root in
app.component.ts
10 applyBrandTokens(config: TenantConfig) {
11 const root = document.documentElement;
12 root.style.setProperty('--linq-
primary',    config.primaryColor);
13 root.style.setProperty('--linq-agency-
name', config.agencyName);
14 this.logoUrl = config.logoUrl;  //
bound to <img> in nav
15 }
16
17 // 3. @linq/snackpaq components use CSS
variables
18 // Buttons, nav highlights, active states
all inherit --linq-primary
19 // No component code changes between
states

<!-- EXTRACTED from knowledge/inbox/CSN-Annual Rate Updates-140826-133117.pdf on 2026-09-09T13:30:40Z -->
<!-- DO NOT EDIT. If extraction is wrong, fix the extractor and re-run. A
     hand-patched extraction no longer matches its source, and once that is
     true of one file no citation in this corpus can be trusted. -->


<!-- page: 1 -->
Annual Rate Updates
3 Types of Annual Changes
Agency rename (June 1, 2026): USDA renamed the Food and Nutrition Service (FNS) to
the Food and Nutrition Administration (FNA). Federal Register publications now use "FNA."
Report numbers (FNS-10, FNS-44, FNS-418, FNS-640, FNS-905) retain their original
designations and are unchanged.
ClaimLaws: rates frozen at application approval. A revised claim in December uses the rate frozen in
October — not the new July rate.
What
Chang
es
Free lunch rate, reduced rate, paid rate,
severe need lunch rates, performance-
based reimbursement factor, breakfast
rates, snack rates, SFSP operating +
administrative rates, CACFP center rates
(breakfast/lunch/snack/supper), DCH Tier
I / Tier II rates, special milk rates, state
match rates
Meal pattern
requirements
(added sugar
limits SY2025-
26, sodium
Target 2
SY2027-28),
Buy American
enforcement
thresholds
(10%→8%→5%
Review instrument
question sets
(ReviewVersions), annual
checklist required items,
VCA scoring tool weights,
FNS report formats,
annual form types (FSMC
certification, food safety,
non-discrimination), Buy
American attestation
language, income
(Most frequent · January (SFSP) and
July (NLSB/SBC/CACFP)every year)
USDA publishes new reimbursement
rates. Data change only — zero code,
zero deployment.
RATE CHANGES 
(Less frequent
· Every 1–5
years)
USDA changes
HOW the math
works. Requires
code — but
safely behind a
program-year
gate.
CALCULATION
RULE
CHANGES (Timeline Varies)
USDA updates annual
forms, review questions,
checklist requirements,
VCA scoring. Data
change via Forms Engine.
FORM & INSTRUMENT
CHANGES
<!-- page: 2 -->
), whole milk
eligibility rule
change (June
2026), non-
congregate
eligibility for
NSLP/SSO
(added
PY2024), CEP
claiming %
formula (has not
changed but
could), 60-day
submission
deadline
exceptions
eligibility guideline
thresholds (July 1
annually)
Frequ
ency
Every July 1 (federal school year start)
and January 1. USDA publishes in Federal
Register ~July each year. Example: 
National School Lunch Program —
National Average Payments SY2025-26,
published July 2025.
Every 1–5 years.
Often
announced 1–2
years in
advance (e.g.,
Healthy Meals,
Healthy Kids
Act 2022 →
non-congregate
effective 2022;
sodium Target 2
announced
2024 →
effective 2027).
Income eligibility
guidelines: annually (July
1). Review instruments:
every 1–3 years. Annual
form text: varies. USDA
often announces in SP
(School Programs)
memos months in
advance.
New
Appro
ach
 INSERT new rows into 
ClaimRateAmounts  in cnp_global with
EffectiveDate = July 1 . No code
change. No SP change. Rate lookup is
effective-dated so  claims always use the
rate in effect on their claim date.
 Implement
the new rule in
C# behind a 
program year
gate: if
(programYea
 Insert new 
ReviewVersion  rows,
new AnnualFormType
rows, new 
VCAScoringTool
versions, updated income
<!-- page: 3 -->
ProgramRatePeriods  defines the
valid window for each program group
year (SFSP: Jan 1–Dec 31;
NSLP/SBP/CACFP: July 1–June 30) and
governs which EffectiveDate is valid for
each program. 
r >= 2024) .
Feature flag
controls
whether the
new logic is
active.
Characterizatio
n tests verify
PY2023 claims
still work under
old rules;
PY2024 claims
work under new
rules. Ship
before effective
date.
thresholds into 
cnp_global. All effective-
dated. Forms Engine
loads the version current
for the program year.
Historical forms (PDF
snapshots) capture what
existed at time of
submission.
Existi
ng
Appro
ach
Current: manually update SQL Server
rate tables per state. 
Current:
update the SP.
No tests.
Deploy per
state. States
end up on
Current: create
SponsorApp54 alongside
SponsorApp34. Over
time: 847 nearly-identical
pages per state. Bug
fixes in one need to be
1 -- NSLP/SBP/CACFP annual update (July
1) 
2 INSERT INTO ClaimRateAmounts
(ProgramCode, MealType, EligCategory,
Rate, EffectiveDate)
3 VALUES ('NSLP', 'Lunch', 'Free', 4.12,
'2025-07-01')
4
5 -- SFSP annual update (January 1)
6 INSERT INTO ClaimRateAmounts
(ProgramCode, MealType, EligCategory,
Rate, EffectiveDate)
7 VALUES ('SFSP', 'Lunch', 'Free', 5.10,
'2026-01-01')
Rate Availability Constraint
ClaimRateAmounts  rows for the
new school year must exist before
any claim with a July 1+ claim date
(or January 1+ for SFSP) can pass
rate validation. The platform does
not block claim submission — rate
lookup returns null and the claim
fails validation at processing time.
Inserting rates before the school
year start is an operational
obligation. USDA typically publishes
in late June; target INSERT
completion before June 30 to avoid
any July 1 claim failures.
<!-- page: 4 -->
Annual Calendar 
ClaimLaws  Preventing Rate-change Errors
different SP
versions.
Regressions
can be
introduced for
prior-year claim
revisions.
manually applied to
others.
MAY
Final rule publications
for upcoming SY
JUNE
Rates published for
next SY
SFSP begins
Load new rates into
cnp_global
JULY
New rates effective for
NLSP/SBC/CACFP
SY start
Income eligibility
guidelines
AUGUST
SY applications open
Buy American SY
enforced
SEPTEMBER
SFSP ends (most
states)
OCTOBER
New FFY starts (Oct 1)
FFY rollover runs
October enrollment
survey
NOVEMBER
USDA publishes next
SY rate proposals
DECEMBER
Application deadlines
many states
JANUARY
Mid-year review
window
New rates effective for
SFSP
FEBRUARY
President's budget —
advance notice of rate
direction
MARCH
Income eligibility
guidelines published
(Federal Register)
Effective July 1
APRIL
USDA publishes SP
memos with guidance
updates
Application
Approved
(Dec 1, 2024) 
ClaimLaws
Record
Created 
July 1, 2025 —
New SY2026
Rates  
Published
October 2025
Claim
Submitted  
(SY2025)
Revised Claim
Submitted Dec
2025
<!-- page: 5 -->
State-Specific vs. Federal  The Overlay Model
State agency
approves
SY2025
application for
Salt Lake City
SD. System
calls 
ClaimLaws.F
reezeOnAppr
oval(applic
ationId) .
ClaimLawsId
: 8821
Application
Id: 12345
EffectiveDa
te: 2024-
12-01
LunFrRte:
4.12
(SY2025)
PbrRte:
0.09 (perf-
based)
BrkFrRte:
2.27
...all
rates
frozen
New rates
inserted into 
ClaimRateAm
ounts :
LunFrRte:
4.28
(SY2026)
EffectiveDate:
2025-07-01
Existing
ClaimLaws
#8821
unchanged.
Claim
validation
loads 
ClaimLawsId
: 8821
(frozen at
approval).
Uses 
LunFrRte:
4.12  — the
SY2025 rate. 
Correct.
New SY2026
applications
get 
LunFrRte:
4.28  frozen
into their
ClaimLaws.
Also correct.
Revision still
references 
ClaimLawsId
: 8821 . Still
uses SY2025
rate 4.12 .
Federal audit
requirement:
the rate in
effect at
original
submission
governs the
claim. 
Free lunch rate $4.12 — every stat
CEP claiming formula ISP × 1.6 (capped
100%)
60-day submission
deadline
Federal mandate
SFSP 2% second
meal cap
Federal — 2% of first
meals
DCH Tier I/II
determination criteria
Census low-income
threshold
Federal (Same for All States) → cnp_global
State match rate Utah: $0.02/eligible
lunch · Most states: $0
Severe Need Lunch
eligibility
determination
State tracks which
sponsors qualify
based on poverty dat
Late claim override
policy
Utah allows late claims
as originals; other
states don't
State-Specific → cnp_ops per-tenant
config + IAccountingExporter
<!-- page: 6 -->
The Annual Rate Update Workflow — How It Should Work
AI MONITOR
Federal Register API detects rate publication Automated
The AI Regulatory Detection service (monitoring Federal Register API daily) classifies the new
document as a Type 1 rate change affecting NSLP/SBP/SFSP/CACFP. Note: USDA renamed FNS
Section 4/11 split
formula
Federal — FNS-10
reporting
Income eligibility %
(130%/185%)
Federal percentage
Non-congregate
PY2024 gate (NSLP)
Federal — PY ≥  2024
Provision 2/3
provisional % (prior
year data)
Federal formula
SSO participation State elects to offer
SSO; most but not all
do
SFSP site High/Low
cost classification
State assigns based
on sponsor type and
operating costs
Accounting system
exporter
UT: USAS · CO:
COFRS · SC:
CALSTARS · MT:
SABHRS
DC source feeds
(IDcFeedAdapter)
UT: Medicaid+SNAP ·
IN:
SNAP+Medicaid+TANF
+DCS · varies —
handled by 
IDcFeedAdapter per
tenant (one of the four
core adapter
interfaces)
Buy American
enforcement
threshold
Federal minimum +
state may add stricter
requirements
Training
requirements
beyond federal
minimum
Some states require
additional Professional
Standards hours
<!-- page: 7 -->
→ FNA on June 1, 2026; Federal Register document headers now use "FNA". Sends alert to
platform team with source document, affected programs, and effective date. Typically fires in
June–July when USDA publishes.
PLATFORM TEAM
AI rate extraction service parses published rates (AI-Assisted)
LLM reads the Federal Register PDF table, extracts all rate values by program and meal type,
maps them to the ClaimRateAmounts schema. Output: a typed JSON object. Takes ~2 minutes
vs. hours of manual work. Human reviews the extracted rates against the published document.
PLATFORM TEAM
Proposed rates staged for review (Human review)
Extracted rates appear in a review UI: new rate vs. prior year, delta %, effective date. Any
change >10% from prior year is hard-blocked for manual verification — anomaly detection
prevents entry errors. State match rates reviewed separately per state.
SYSTEM
Approved rates INSERT into cnp_global(Zero deployment)
INSERT INTO ClaimRateAmounts (ProgramCode, MealType, EligCategory, Rate,
EffectiveDate) VALUES ('NSLP', 'Lunch', 'Free', 4.12, '2025-07-01')
No code change. No SP change. No deployment to any state. All 22 states get the new rates
simultaneously and correctly at effective date.
APPLICATIONS
New SY applications freeze new rates into ClaimLaws(Automatic)
When state agencies approve SY2026 applications, ClaimLaws.FreezeOnApproval() captures
the eligibility snapshot; dollar rates are resolved separately from ClaimRateAmounts at claim
time. SY2025 applications retain SY2025 frozen rates. Both are correct simultaneously, for all 22
states, without any manual intervention.
<!-- page: 8 -->
What the Calculation Looks Like (C# vs. Sproc)
With this approach: updating rates = one database INSERT. Adding a new state = no rate code
changes. State-specific overrides (state match, severe need eligibility, SSO rates) live in
ClaimLaws — not in if/else branches. The characterization tests verify that rounding, Section
4/11 splits, and severe need logic all produce identical output to the legacy SP before any SP is
retired.
1 // The NSLP claim reimbursement calculation — translated from
NslpSponsorClaimBLL.CalcReimbursement()
2 // This is the actual math. The key insight: rates come from ClaimLaws (frozen), not live
tables.
3
4 public class NslpReimbursementService {
5
6 public ReimbursementResult Calculate(ClaimContext ctx, ClaimLaws laws) {
7
8 // Step 1: Select rate set based on sponsor eligibility (from ClaimLaws — frozen at
approval)
9 var lunFrRte = laws.SeverNeedLunch ? laws.SnlFrRte : laws.LunFrRte;
10 var lunRdcRte = laws.SeverNeedLunch ? laws.SnlRdcRte : laws.LunRdcRte;
11 var lunPdRte  = laws.SeverNeedLunch ? laws.SnlPdRte : laws.LunPdRte;
12
13 // Step 2: Add Performance-Based Reimbursement if sponsor qualifies
14 if (laws.PerformanceBasedQualified) {
15 lunFrRte  += laws.PbrRte;   // ~$0.09 SY2025-26
16 lunRdcRte += laws.PbrRte;
17 lunPdRte  += laws.PbrRte;
18 }
19
20 // Step 3: Section 4/11 split (FNS-10 federal reporting requirement)
21 // Section 4 = base subsidy (ALL meals get this rate)
22 // Section 11 = additional subsidy for free/reduced above the paid rate
23 var lun4Amt  = Round((ctx.FreeLunches + ctx.SSOLunches) * lunPdRte);
24 var lun11Amt = Round((ctx.FreeLunches + ctx.SSOLunches) * (lunFrRte - lunPdRte));
25 var lunRdc4  = Round(ctx.ReducedLunches * lunPdRte);
26 var lunRdc11 = Round(ctx.ReducedLunches * (lunRdcRte - lunPdRte));
27
28 // Step 4: Calculate all meal type amounts
29 var result = new ReimbursementResult {
30 LunchPaidAmt    = Round(ctx.PaidLunches * lunPdRte),
31 LunchFreeAmt    = Round(ctx.FreeLunches * lunFrRte),
32 LunchReducedAmt = Round(ctx.ReducedLunches * lunRdcRte),
33 LunchWaiverAmt  = Round(ctx.SSOLunches * (laws.SfspRates ? laws.SsoLunWavRte :
lunFrRte)),
34 BrkFreeAmt      = Round(ctx.FreeBreakfasts * laws.BrkFrRte),
35 StateMatchAmt   = Round(ctx.StateMatchEligLunches * laws.StateMatchRte),
36 FFVReimbAmt     = ctx.FFVAdminCost + ctx.FFVOperCost,
37 Lun4Amt = lun4Amt, Lun11Amt = lun11Amt,  // FNS-10 reporting
38 };
39
40 // Step 5: Net = gross - prior revision amounts (for revised claims)
41 result.NetReimbAmt = result.Total - ctx.PriorRevisionTotal;
42 return result;
43 }
44
45 // DISUtil.Round() — MidpointRounding.AwayFromZero — MUST match legacy exactly
46 private static decimal Round(decimal value) =>
47 Math.Round(value, 4, MidpointRounding.AwayFromZero);
48 }
<!-- page: 9 -->
Current Rates & Annual Changes 
📋  SY2026-27 rates expected from USDA FNA in July 2026. When published: INSERT into 
cnp_global.ClaimRateAmounts  with EffectiveDate = 2026-07-01 . Zero code
change. Zero deployment. First POC of the new rate update model.
Free Lunch NSLP $4.05 $4.12 USDA annual
publication
(July)
No — federal.
State match
added on top.
Reduced
Lunch
NSLP $3.75 $3.82 USDA annual
publication
No
Paid Lunch NSLP $0.47 $0.50 USDA annual
publication
No
Severe Need
Lunch (Free)
NSLP $4.35 $4.42 USDA.
Sponsor must
qualify via
poverty data.
Qualification
is state-
determined;
rate is federal
Performance
-Based
Reimburseme
nt
NSLP $0.08 $0.09 USDA. Added
to ALL lunch
rates if school
meets
nutrition
standards.
Qualification
is state-
tracked; rate
is federal
Free
Breakfast
SBP $2.21 $2.27 USDA annual
publication
No
Severe Need
Breakfast
SBP $2.57 $2.64 USDA. ≥ 40%
free/reduced
enrollment
qualifies.
Qualification
threshold is
federal; state
tracks
eligibility
SFSP
Operating
SFSP $4.43 $4.56 USDA annual
publication
No
Rate Program SY2024-25 SY2025-26 What can
change it
State-
specific?
<!-- page: 10 -->
Rate (Lunch)
SFSP
Administrativ
e Rate (High)
SFSP $0.24 $0.25 USDA. High vs
Low
determined by
site type/cost.
Site
classification
is state-
determined
CACFP
Breakfast
(Free)
CACFP $1.46 $1.51 USDA annual
publication
No
CACFP Lunch
(Free)
CACFP $3.25 $3.34 USDA annual
publication
No
DCH Tier I
Lunch
DCH $1.47 $1.52 USDA. Tier I =
provider in
low-income
area OR
provider
income is low.
Tier
determination
is
state/census-
data driven
DCH Tier II
Low Lunch
DCH $0.97 $1.00 USDA annual
publication
No
SSFO SSFO Uses SFSP operating +
administrative rates — no
separate rate table. Same
OprLunRte,
AdmLunRteHigh/Low as SFSP.
No — follows
SFSP rates
exactly
State Match
Rate
NSLP Varies Varies State
legislature.
Utah
~$0.02/eligibl
e lunch. Most
states: $0.
YES — fully
state-
specific.
Stored per-
tenant in
cnp_global.
Free Meal
Threshold
All 130% poverty 130% poverty Percentage is
federal. Dollar
amount
updates with
No — federal
percentage,
federal
<!-- page: 11 -->
poverty
guidelines
(March each
year).
poverty
guideline
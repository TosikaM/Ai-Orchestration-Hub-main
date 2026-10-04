# Federal math, rates, and the ClaimLaws freeze

## The core equation {#core}

**Meals Served × Reimbursement Rate = Federal Payment.** USDA does not pay schools directly:
USDA pays the state agency, and the state pays the school districts. The math happens at every
level of that chain.
<!-- source: CSN-The Math-140826-133113.md#page-1 -->

Three eligibility categories — Free, Reduced, Paid — each with its own rate, because USDA pays
more for meals served to children from lower-income households. A child lands in a category
either by a household income application reviewed by staff, or by **Direct Certification** (an
overnight match against SNAP and Medicaid records, which certifies Free with no application at
all).
<!-- source: CSN-The Math-140826-133113.md#page-1 -->
<!-- source: CSN-The Math-140826-133113.md#page-2 -->

## The problem ClaimLaws solves {#claimlaws-problem}

USDA publishes new rates every 1 July. What happens to a claim submitted before 1 July but
revised after it?

**The answer is always the rate for the original claim month.** A revised claim for October
2024 processed in August 2025 uses the October 2024 rate. Before this mechanism existed, a
July rate update would silently change the reimbursement on every prior-year revised claim
that got reprocessed — a district disputing an October 2024 claim would find it recalculated
at the July 2025 rate, which is wrong.
<!-- source: CSN-The Math-140826-133113.md#page-2 -->

The stated design intent is that ClaimLaws makes that *structurally impossible* rather than
procedurally discouraged.
<!-- source: CSN-The Math-140826-133113.md#page-2 -->

## What ClaimLaws stores {#claimlaws-contents}

> **This is the most consequential unresolved contradiction in the corpus.** The design
> documents state that ClaimLaws stores the eligibility tier and **not** dollar rates; the
> reference C# implementation reads dollar rates directly off the ClaimLaws object. The two
> cannot both be built. See `99-contradictions-and-open-questions.md#claimlaws-rates` before
> designing this table or the claim calculation service.

**The stated design decision**, appearing in three documents in near-identical words:

> The eligibility snapshot (enrollment counts, rate tier qualifications, site program
> configuration) is captured from the approved application and never modified. Dollar rates
> are **not** stored in ClaimLaws — they are resolved at claim calculation time from
> `ClaimRateAmounts` using the claim date as the effective date key.
<!-- source: CSN-Data-140826-132933.md#page-4 -->
<!-- source: CSN-The Math-140826-133113.md#page-2 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-12 -->

Under that design ClaimLaws holds: the eligibility tier (standard vs severe need), the
applicable meal groups, operating parameters, enrollment counts, CEP ISP percentage,
performance-based eligibility, site program configuration, and the effective date range.
<!-- source: CSN-The Math-140826-133113.md#page-3 -->
<!-- source: CSN-Data-140826-132933.md#page-13 -->

The reason given for the separation is that it *"makes annual rate updates a data-only
operation with no reprocessing of existing approvals."* Two mechanisms work together:
ClaimLaws prevents application changes from retroactively altering a sponsor's tier
qualifications on already-processed claims; `ClaimRateAmounts` effective-dating ensures a
revised prior-year claim resolves to the rate in effect on its original claim date.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-13 -->
<!-- source: CSN-Data-140826-132933.md#page-13 -->

## The freeze is immutable {#immutability}

- Created **automatically** the moment an application is approved — the sole trigger.
- Cannot be edited or deleted by anyone through any interface or administrative capability.
  **There is no "correct a mistake" edit path**; a genuine correction requires a new,
  separately recorded action.
- Later rule or rate changes never retroactively affect an existing frozen record.
- The values shown to a user must exactly match what was stored — there is no separate
  "display" version that could drift.
- Visible on the application record after approval, not just stored invisibly.
- **One generic mechanism serves every program**, driven by configuration — directly replacing
  what are today multiple separate program-specific procedures.
<!-- source: 06_FRD_Rate_Freeze.md#section-3 -->
<!-- source: 06_FRD_Rate_Freeze.md#section-4 -->

The snapshot reflects the rules in force **at the literal moment of approval** — not at
submission, not at review.
<!-- source: 06_FRD_Rate_Freeze.md#section-4 -->

The Phase 1 acceptance test is concrete: `ClaimLaws` rows have no UPDATE endpoint; an attempt
returns HTTP 405.
<!-- source: CSN-Prototype-140826-133159.md#page-12 -->

## Annual rate updates — the zero-deployment claim {#rate-updates}

The architectural proof point: applying new USDA rates is a **single database INSERT into
`cnp_global.ClaimRateAmounts`** that takes effect for all states simultaneously. No code
change, no stored-procedure change, no per-state deployment.

```sql
INSERT INTO ClaimRateAmounts (ProgramCode, MealType, EligCategory, Rate, EffectiveDate)
VALUES ('NSLP', 'Lunch', 'Free', 4.28, '2026-07-01'), ...
```
<!-- source: CSN-Data-140826-132933.md#page-5 -->
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-2 -->

The contrast with today: in DIS and CTS, rates are often embedded in stored-procedure logic,
not a table. A rate change means finding every SP that referenced the old rate, updating each,
testing, and deploying per state — leaving states on different SP versions and allowing
regressions in prior-year claim revisions.
<!-- source: CSN-The Math-140826-133113.md#page-10 -->
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-3 -->

### Three types of annual federal change {#change-types}

| Type | Frequency | Response |
|---|---|---|
| **Rate changes** | Every 1 July (NSLP/SBP/CACFP) and 1 January (SFSP) | INSERT rows. Zero code, zero deployment |
| **Calculation-rule changes** — USDA changes *how* the math works | Every 1–5 years, usually announced 1–2 years ahead | New rule in C# **behind a program-year gate** (`if (programYear >= 2024)`), feature-flag controlled, with characterization tests proving prior-year claims still work under old rules. Ship before the effective date |
| **Form & instrument changes** — annual forms, review questions, checklists, VCA scoring, income guidelines | Income guidelines annually (1 July); review instruments every 1–3 years | Insert new `ReviewVersion`, `AnnualFormType`, `VCAScoringTool` rows, all effective-dated. The Forms Engine loads the version current for the program year |
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-1 -->
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-2 -->
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-3 -->

### The anomaly gate {#anomaly-gate}

USDA occasionally publishes corrections and **has issued erroneous rate documents before**.
Any rate change greater than **10%** from the prior year is hard-blocked for mandatory human
verification against the official Federal Register document before the INSERT is allowed. A
3–4% annual increase is normal inflation adjustment; a 15% jump is suspicious.
<!-- source: CSN-The Math-140826-133113.md#page-10 -->
<!-- source: CSN-The Math-140826-133113.md#page-11 -->
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-7 -->

### The rate availability constraint {#rate-availability}

Rows for the new school year **must exist before any claim with a 1 July+ claim date** (or
1 January+ for SFSP) can pass rate validation. The platform does not block submission — the
rate lookup returns null and the claim fails validation at processing time. USDA typically
publishes in late June; the INSERT should complete before 30 June. *"Inserting rates before
the school year start is an operational obligation."*
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-3 -->

The rollover job and the rate insertion are independent operations. Rollover creates the new
`ProgramGroupYear` and seeds application shells; it does not require rates to be present. **A
new program year with no rates is valid**; a claim against it fails rate validation until rates
exist. Both must complete before claims can be processed.
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-5 -->

### The agency rename {#fns-to-fna}

USDA renamed the Food and Nutrition **Service (FNS)** to the Food and Nutrition
**Administration (FNA)** effective 1 June 2026. Federal Register publications now use "FNA."
**Report numbers — FNS-10, FNS-44, FNS-418, FNS-640, FNS-905 — retain their original
designations and are unchanged.**
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-1 -->

## Community Eligibility Provision (CEP) {#cep}

High-poverty schools may skip individual household income applications and serve all students
free meals. USDA still needs to know what to pay, so it estimates reimbursement from how many
students are directly certified.

```
ISP = Identified Students ÷ Total Enrollment × 100      (must be ≥ 40% to qualify)
Claiming % = ISP × 1.6                                   (capped at 100%)
```

**The 1.6 multiplier is federal law — 42 U.S.C. § 1759a(a)(1)(F)(viii) — and cannot be
configured. Any attempt to make it configurable would constitute a federal compliance
violation.**
<!-- source: CSN-The Math-140826-133113.md#page-4 -->
<!-- source: CSN-The Math-140826-133113.md#page-5 -->

**CEP Groups**: a district can pool schools into a group, combining enrollment and identified
students into one ISP calculation, which helps schools just under the threshold. Worked
example: Lincoln 71.6%, Roosevelt 47.4%, Jefferson 34.1% (individually failing) — pooled as
615 ÷ 1,202 = 51.2% ISP → 81.9% claiming %, and all three join CEP together.
<!-- source: CSN-The Math-140826-133113.md#page-4 -->

CEP is modelled as an attribute on ClaimLaws (`CEP_ISP_Pct`), **not** as a row in
`FederalProgramDefinitions` — it is a claiming option within NSLP, not a standalone program.
It nevertheless gets its own bounded context because the ISP math needs isolation, and the DIS
`CnpCepApi` already proved that boundary works.
<!-- source: CSN-Data-140826-132933.md#page-47 -->
<!-- source: CSN-Platform Domains-140826-133136.md#page-4 -->

## Provisions 2 and 3 {#provisions}

Older paperwork-reduction schemes, both still in use.

**Provision 2** — establish a base year by collecting full household applications once and
measuring accurate Free/Reduced/Paid percentages. For the next three non-base years, claim
using those percentages against total meals served, with no new applications. Worked example:
base year 68% / 12% / 20%; September's 22,840 lunches yield 15,531 Free × $4.28 + 2,741
Reduced × $3.97 + 4,568 Paid × $0.53 = $79,775.49.
<!-- source: CSN-The Math-140826-133113.md#page-5 -->

**Provision 3** — captures richer base-year data (both claiming percentages and eligibility
percentages) and projects non-base-year meals from **enrollment and operating days alone**. In
a non-base year the sponsor enters only current enrollment and number of operating days; the
system scales the base-year meal count proportionally, applies base-year claiming percentages,
and feeds the result into the standard calculation at current rates. There is no separate
inflation adjustment. Far less common than Provision 2.
<!-- source: CSN-The Math-140826-133113.md#page-5 -->
<!-- source: CSN-The Math-140826-133113.md#page-6 -->

The compliance consequence: for Provision schools there are no individual eligibility records
for non-base years to compare meal counts against, **which is why four separate fiscal
workbook variants exist.**
<!-- source: CSN-The Math-140826-133113.md#page-6 -->

## CACFP {#cacfp}

Same Meals × Rate principle, but the rate depends on the **type of provider**, not just the
child's income level. Day care homes are divided into two tiers based on the provider's own
income or the neighbourhood's income level. Centres claim at a single rate based on enrolled
children's individual eligibility; homes use the Tier I/II system.
<!-- source: CSN-The Math-140826-133113.md#page-6 -->
<!-- source: CSN-The Math-140826-133113.md#page-7 -->

Stricter meal patterns than school programs: a CACFP breakfast must include a grain, a milk,
and a fruit or vegetable; a lunch a meat/meat alternate, a grain, two different vegetables or
fruits, and milk. **Meals that do not meet the pattern are disallowed even if the count is
correct.**
<!-- source: CSN-The Math-140826-133113.md#page-7 -->

**Meal limit:** a maximum of two meals and one snack per child per day, or one meal and two
snacks. A child cannot be claimed for three full meals. Enforced in claim validation, and
locked federally (`CACFP.MealLimitPerChildPerDay`, 7 CFR 226.20).
<!-- source: CSN-The Math-140826-133113.md#page-7 -->
<!-- source: CSN-Configuration Defaults-140826-132750.md#page-6 -->

**FDCH tier certification windows are evidence-based, not configurable:** Tier I based on
census tract or school eligibility = 60 months; Tier I based on provider income = 12 months.
Neither can be shortened by state config.
<!-- source: CSN-Data-140826-132933.md#page-7 -->

## SFSP and SSFO {#summer}

Summer programs operate as open sites where any child 18 or under who shows up eats free. No
applications, no eligibility sorting, no Free/Reduced/Paid categories — **one rate per meal
type.**
<!-- source: CSN-The Math-140826-133113.md#page-7 -->

Sites must record **actual attendance** rather than projecting counts; a **50% attendance cap**
applies at some site types when actual attendance records are unavailable. A federal **2%
second-meal cap** also applies, calculated at sponsor level.
<!-- source: CSN-The Math-140826-133113.md#page-7 -->
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-5 -->
<!-- source: CSN-Platform Domains-140826-133136.md#page-4 -->

**Non-congregate service** was permanently allowed after COVID for some sites — grab-and-go,
parent pick-up, delivery — with stricter recordkeeping. Three modes are enforced: congregate
only, non-congregate only, and mixed (each tracked separately).
<!-- source: CSN-The Math-140826-133113.md#page-8 -->

**SSFO** lets NSLP schools keep serving through summer under school-year administrative rules
with summer funding, from a different federal grant account. It has its own ClaimLaws and
site-application rules and ~16 dedicated tables, keeping SSFO quirks from bleeding into NSLP
claim validation.
<!-- source: CSN-The Math-140826-133113.md#page-8 -->
<!-- source: CSN-Data-140826-132933.md#page-33 -->

SFSP rates are higher per meal than NSLP free rates because SFSP is fully federally funded —
no state funds, no family copayments — and summer-only operations carry higher administrative
cost.
<!-- source: CSN-The Math-140826-133113.md#page-8 -->

## FFVP — a different financial instrument entirely {#ffvp}

Not meals × rate. USDA gives selected schools a fixed annual dollar allocation based on
enrollment (approximately $50–$75 per student), spent on fresh produce served as snacks.

```
Annual Allocation = Enrolled Students × Per-Student Amount
```

Only high-poverty elementary schools qualify, typically 50%+ free/reduced eligibility, and
**selection is by state agency invitation, not application.** The model is "approved
allocation → expenditure tracking → unexpended balance," and schools submit expenditure
reports rather than monthly meal-count claims.

**There is no ClaimLaws for FFVP** — reimbursement equals actual expenditure, so there is no
rate to freeze.
<!-- source: CSN-The Math-140826-133113.md#page-8 -->
<!-- source: CSN-The Math-140826-133113.md#page-9 -->
<!-- source: CSN-Data-140826-132933.md#page-33 -->
<!-- source: CSN-Data-140826-132933.md#page-34 -->

## Fiscal action math {#fiscal-actions}

When a review finds a sponsor claimed more meals than served, or meals not meeting program
requirements, the state must calculate repayment. USDA prescribes four formula variants:

| Variant | Applies to |
|---|---|
| **FA1** | Standard NSLP/SBP schools — difference between claimed and correct, across the full school year |
| **FA2** | Provision 2/3 schools — cannot measure against individual eligibility records, so a different calculation; three sub-variants (Standard, Provision2, Provision3) |
| **FA3** | Provision 2/3 split, different disallowance methodology; USDA sometimes requires fiscal action at **site** level rather than sponsor level |
| **FA4** | Non-creditable meals — claimed but not meeting meal pattern requirements |
<!-- source: CSN-The Math-140826-133113.md#page-9 -->
<!-- source: CSN-Data-140826-132933.md#page-24 -->
<!-- source: CSN-Data-140826-132933.md#page-25 -->

A **recalculation layer** preserves the original calculation alongside the revised one when a
sponsor disputes a fiscal action or provides additional documentation, so both are auditable.
<!-- source: CSN-Data-140826-132933.md#page-25 -->

### The five-day reconciliation {#five-day}

The most common finding source. A reviewer samples five days from a recent month's claim and
compares kitchen production records against claimed counts, extrapolating any gap across the
year.

Worked example (Provo City Schools, a Provision 2 school): 312-meal gap over 5 sample days,
21 operating days in September →
`312 ÷ 5 × 21 = 1,310 estimated overclaimed meals`; `1,310 × $4.05 blended rate = $5,305.50`
assessed repayment.
<!-- source: CSN-The Math-140826-133113.md#page-9 -->
<!-- source: CSN-Data-140826-132933.md#page-21 -->

### Why fiscal actions live in Compliance, not Accounting {#fiscal-action-domain}

The **calculation** of what is owed is an enforcement function tied to the review record; the
**collection** (repayment schedules, receivables, cheques received) is a financial instrument
and belongs to Accounting. Accounting receives only the final assessed amount and never needs
to know whether FA1, FA2, FA3 or FA4 was used.

Putting fiscal actions in Accounting would create a circular dependency: Accounting would need
to read review findings from Compliance to generate them.
<!-- source: CSN-Data-140826-132933.md#page-29 -->
<!-- source: CSN-The Math-140826-133113.md#page-9 -->

## Rounding must match the legacy exactly {#rounding}

`Math.Round(value, 4, MidpointRounding.AwayFromZero)`. The reference implementation flags this
as **MUST match legacy exactly**, and characterization tests are required to verify that
rounding, Section 4/11 splits and severe-need logic produce identical output to the legacy
stored procedure before any SP is retired.
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-8 -->

## The Section 4/11 split {#section-4-11}

An FNS-10 federal reporting requirement, not an internal accounting nicety.
Section 4 is the base subsidy that **all** meals receive at the paid rate; Section 11 is the
additional subsidy for free/reduced meals above the paid rate:

```
lun4Amt  = Round((FreeLunches + SSOLunches) × lunPdRte)
lun11Amt = Round((FreeLunches + SSOLunches) × (lunFrRte − lunPdRte))
```

Utah is the reference implementation for states with both federal and state-funded meal
programs.
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-8 -->
<!-- source: CSN-Data-140826-132933.md#page-40 -->

## Federal vs state-specific — the overlay {#federal-vs-state}

| Federal, identical everywhere → `cnp_global` | State-specific → `cnp_ops` config + adapters |
|---|---|
| Free lunch rate | State match rate (Utah ~$0.02/eligible lunch; most states $0) |
| CEP claiming formula ISP × 1.6 | Severe Need lunch eligibility determination (state tracks which sponsors qualify from poverty data) |
| 60-day submission deadline | Late claim override policy (Utah allows late claims as originals; other states do not) |
| SFSP 2% second-meal cap | SSO participation (state elects; most but not all do) |
| DCH Tier I/II determination criteria | SFSP site High/Low cost classification |
| Section 4/11 split formula | Accounting system exporter (UT: USAS · CO: COFRS · SC: CALSTARS · MT: SABHRS) |
| Income eligibility % (130% / 185%) | DC source feeds per tenant |
| Non-congregate PY2024 gate | Training requirements beyond federal minimum |
| Provision 2/3 provisional % formula | Buy American stricter-than-federal additions |
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-5 -->
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-6 -->

## The annual calendar {#calendar}

| Month | Event |
|---|---|
| May | Final rule publications for the upcoming school year |
| June | Rates published for next SY; SFSP begins; load new rates into `cnp_global` |
| July | New rates effective for NSLP/SBP/CACFP; SY starts; income eligibility guidelines |
| August | SY applications open; Buy American SY enforced |
| September | SFSP ends in most states |
| October | New federal fiscal year; FFY rollover runs; October enrollment survey |
| November | USDA publishes next SY rate proposals |
| December | Application deadlines in many states |
| January | Mid-year review window; new rates effective for SFSP |
| February | President's budget — advance notice of rate direction |
| March | Income eligibility guidelines published in the Federal Register, effective 1 July |
| April | USDA publishes School Programs memos with guidance updates |
<!-- source: CSN-Annual Rate Updates-140826-133117.md#page-4 -->

## Regulatory sources {#regulatory-sources}

7 CFR Part 210 (NSLP) · Part 220 (SBP) · Part 225 (SFSP) · Part 226 (CACFP). Plus NIST SP
800-171 (the 110 CUI security requirements), FERPA (34 CFR Part 99), the Federal Register API
(the feed the policy-change detection service monitors), and the annual Income Eligibility
Guidelines.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-14 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-15 -->

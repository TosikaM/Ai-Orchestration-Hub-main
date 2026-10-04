# The application-to-approval journey

This is the Phase 1 flow end to end — the one thing the October prototype must do.

## The cast {#actors}

| Role | What they do |
|---|---|
| **Sponsor Director / Staff** | The organization applying — a school district, daycare centre, summer camp operator. Submits and manages applications for their own organization only |
| **Caseworker** | State agency staff; helps applicants and does first-pass review, advances or returns |
| **Reviewer** | State agency staff; formal review and the approve/deny determination |
| **State Agency Admin** | Oversees the process, broader state-wide visibility, can configure |
| **The System** | Runs background checks and enforcement automatically, no human needed |
| **LINQ Config Admin** | Platform configuration administrator; manages tenant-level program settings |
<!-- source: Application-to-Approval-Journey.md#cast -->
<!-- source: 00_FRD_Index.md#section-4 -->

## The stages {#stages}

### Stage 1 — Prospect (state-configurable) {#prospect}

Some states let a prospective sponsor register interest first — a waiting room where basic
info is captured. **This stage does not exist in every state.** Whether Prospect appears is a
setting per state, not a bug — a tester seeing it in State A and not State B is seeing correct
behaviour.
<!-- source: Application-to-Approval-Journey.md#stage-1 -->

Architecturally, `Prospect` is a DIS-specific capability (PotentialSponsor tracking) absent
from base CTS. It is `IsFederal = false`, so it can be present in DIS-origin tenants and
absent from CTS-origin tenants via `TenantTransitionOverrides` without touching the federal
compliance chain. `PendingDocs` is similarly state-configurable.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-10 -->

### Stage 2 — Draft {#draft}

The sponsor fills out the real form. They can save partial progress and return; nothing is
official yet.

**Required documents before submission** — a signed agreement and a free/reduced price policy
statement — are **required by federal rule, so no state can turn the requirement off.** The
platform row is a `WorkflowTransitionConditions` entry with
`ConditionCode = 'AllRequiredDocsAttached'`, `IsFederal = true`, and a failure message citing
7 CFR 210.9.
<!-- source: Application-to-Approval-Journey.md#stage-2 -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-14 -->

A state may **add** documents on top (Alaska's site affidavit) via a non-federal override; it
cannot remove the federal ones.
<!-- source: CSN-Workflow Engine-140826-132724.md#page-14 -->

The requirements layer adds: in-progress work is saved and resumable; submission requires
completeness with the system clearly identifying what is missing; validation failures are
recorded and shown to the sponsor, and state-side staff may override a specific failure **only
where configuration explicitly allows it** — never for a federally locked condition.
<!-- source: 03_FRD_Application_Submission.md#section-3 -->

### Stage 3 — Submitted {#submitted}

On submit, the system records who submitted and when, for the audit trail. The sponsor does not
see this directly, but *"if you ever need to prove when something happened, this is where that
answer comes from."*
<!-- source: Application-to-Approval-Journey.md#stage-3 -->

### Stage 4 — Under Review {#under-review}

A Reviewer picks the application off a queue. **The NDL check is not something the Reviewer
manually triggers — it happens as part of the approval attempt.**
<!-- source: Application-to-Approval-Journey.md#stage-4 -->

A Caseworker can either advance the application for further/final review, or **return it to
the sponsor with a required explanation** of what needs correction; the sponsor corrects and
resubmits back into the review process.
<!-- source: 04_FRD_Review_Workflow.md#section-3 -->

### Stage 5 — The determination {#determination}

**Deny** → the application moves to Declined/Denied, recorded permanently.

**Approve** → the system checks the NDL screening result before letting the approval through.
See below.
<!-- source: Application-to-Approval-Journey.md#stage-5 -->

### Stage 6 — The instant approval succeeds {#post-approval}

Two things happen automatically:

1. **A permanent snapshot** of exactly what the application looked like at that moment. *"Like
   a photograph, frozen in time."* Even if related data is edited later, this never changes —
   because months or years later a federal auditor asking "what did this application look like
   the day it was approved?" must get an instant answer, not a manual reconstruction.
2. **The claim eligibility rules lock in** (`FreezeClaimLaws`), which is what unlocks the
   sponsor's ability to submit meal claims. **There is no Edit button for it.** A mistake found
   afterwards is handled as a new correction process, never a quiet fix to the old record.
<!-- source: Application-to-Approval-Journey.md#stage-6 -->

The suggested test is a good one: *"try to find any screen or action that lets you edit this
locked-in record after approval. You shouldn't be able to."*
<!-- source: Application-to-Approval-Journey.md#stage-6 -->

## The NDL check {#ndl}

Federal program rules prohibit approving a sponsor organization, or its named principals, that
has been federally disqualified. **This is a legal compliance requirement, not a business
preference** — which is why it is treated as an absolute, non-negotiable gate rather than an
ordinary business rule.
<!-- source: 05_FRD_NDL_Screening.md#section-1 -->

### Mechanism {#ndl-mechanism}

A named condition hook `NoNDLMatch` with `IsFederal = true` on the `ApproveApplication`
transition, checking three identifying fields against the USDA FNS NDL lookup endpoint:
**organization name, EIN, and the names of key principals** listed on the application
(director, authorized representative).

```
TransitionCode  = 'ApproveApplication'
ConditionCode   = 'NoNDLMatch'
ConditionType   = 'PreCondition'
IsFederal       = true
FailureMessage  = 'Application cannot be approved: NDL match found. Review required
                   before proceeding.'
```
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-1 -->

The check **runs fresh every single time an approval is attempted** — it is not optional, not
skippable, and a previous pass does not exempt a later attempt.
<!-- source: 05_FRD_NDL_Screening.md#section-3 -->

### Three outcomes {#ndl-outcomes}

| Outcome | Behaviour |
|---|---|
| **No Match** | Approval may proceed immediately |
| **Possible Match** | Does not auto-block and does not auto-proceed. Routes to a designated reviewer who must record an explicit decision, via `NdlOverrideRequests` |
| **Confirmed Match** | **Approval is permanently blocked** |
<!-- source: 05_FRD_NDL_Screening.md#section-3 -->

A Confirmed Match is the strongest guarantee in the platform — *"stronger even than the general
permission-override model, because it cannot be reached through any override layer at all."*
No user, administrator, configuration setting or override mechanism of any kind can allow that
application to be approved. It is enforced in code: the `NoNDLMatch` hook returns false for a
ConfirmedMatch **regardless of any `NdlOverrideRequest` outcome.**
<!-- source: 05_FRD_NDL_Screening.md#section-3 -->
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-2 -->

### Segregation of duties {#ndl-sod}

**A reviewer who was also the one who submitted the application, in any capacity, is not
permitted to clear a Possible Match on it.** This exists to protect the integrity of the review
itself.
<!-- source: 05_FRD_NDL_Screening.md#section-4 -->

### Recording {#ndl-recording}

Every screening attempt is permanently recorded regardless of outcome, including the specific
data checked and the result. **The specific criteria that produced the match — organization
name, tax ID, or a named individual — is recorded, not just the fact that a match occurred.**

Two tables in the Applications domain (`cnp_ops`):

- `NdlCheckResults` — written by the hook on **every** `ApproveApplication` attempt.
  `MatchStatus` (NoMatch | PossibleMatch | ConfirmedMatch), `MatchDetails` JSONB, `CheckedBy`
  (System | Manual). Retained permanently.
- `NdlOverrideRequests` — tracks the human investigation of a Possible Match. A `Denied`
  disposition keeps the block active; an `Approved` disposition allows approval to proceed
  **with the override recorded.**
<!-- source: 05_FRD_NDL_Screening.md#section-3 -->
<!-- source: 05_FRD_NDL_Screening.md#section-4 -->
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-2 -->

### Phase 1 stands in a synthetic dataset {#ndl-phase-1}

Using a realistic stand-in dataset instead of the live federal source is explicitly acceptable
for Phase 1, and does not weaken the compliance requirement, because the blocking logic and
audit trail are real regardless of the data source. **What is not acceptable is treating a
match against the stub any differently from a match against the real source.**
<!-- source: 05_FRD_NDL_Screening.md#section-3 -->
<!-- source: 05_FRD_NDL_Screening.md#section-5 -->

In the prototype sprint plan the hook is a *stub returning true*; full NDL integration is
post-prototype.
<!-- source: CSN-Prototype-140826-133159.md#page-11 -->

## Denial and appeal {#appeal}

**A Declined application is not necessarily the end of the story.** A separate case file is
opened *about* the denied application:

```
Filed → Informal Resolution → Formal Hearing → Decision Issued → Closed
```

If the appeal decision goes in the sponsor's favour, **the original application is
reinstated** — a designed, deliberate reversal, implemented via the `ApplyAppealDecision`
action hook which may reverse the parent entity's state.
<!-- source: Application-to-Approval-Journey.md#appeal -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-11 -->

The QA note is worth preserving as an open item: it is not documented **which status a
reinstated application lands in** — straight to Approved, or back to Under Review for a fresh
look.
<!-- source: Application-to-Approval-Journey.md#appeal -->

## Federal vs configurable, in tester's terms {#federal-vs-configurable}

- **🔒 Locked / Federal** — every state behaves identically, no exceptions, and no configuration
  screen even shows an edit option. The required documents before submission; the
  approve/deny decision itself; the NDL background check; the immutable approval snapshot; the
  rate/rule freeze.
- **🔧 Configurable** — states can toggle or tweak. Whether the Prospect stage exists; extra
  state-specific required documents; the number of reviewers in the approval chain; address
  field editability post-approval.

*"If you ever see a 'locked' behavior differ between states, or a state successfully bypass it
— that's the kind of bug worth escalating immediately, because it likely means a federal
compliance rule got broken, not just a cosmetic inconsistency."*
<!-- source: Application-to-Approval-Journey.md#state-variation -->

Every state customization requires a **real written explanation of at least 20 characters** —
"N/A" or "asked to" will not count — saved permanently and undeletable even if the change is
later undone.
<!-- source: Application-to-Approval-Journey.md#state-variation -->
<!-- source: CSN-Workflow Engine-140826-132724.md#page-19 -->

## Configuration in action — a worked example {#config-example}

A Reviewer in Iowa tries to approve:

1. System loads Iowa's config → `REQUIRE_TWO_STAGE_APPROVAL = TRUE`
2. Check passes: this Reviewer has final-approval authority
3. System loads Iowa's config → `ADDRESS_SOURCE = "STATE_EIS"` (an external state system owns
   addresses)
4. Address fields render read-only because the state owns them
5. Approval fires → claim-eligibility data generated per Iowa's rules

A different state with `REQUIRE_TWO_STAGE_APPROVAL = FALSE` and
`ADDRESS_SOURCE = "SPONSOR_ENTERED"` gets the same flow with one approval stage and an
editable address field. **The same code runs everywhere; configuration changes behaviour.**
<!-- source: Application-to-Approval-Journey.md#config-example -->

## External data sources {#external-sources}

Some fields are not entered by anyone in this system — knowing which matters for distinguishing
a bug from correct read-only behaviour.

| Data | Source | Mechanism | Freshness | Who corrects it |
|---|---|---|---|---|
| Addresses (Iowa) | Iowa's Enterprise Information System (EIS) | Database synonym / linked read | Nightly refresh | State EIS team |
| County codes | State reference database | API call | On demand | State GIS/Admin |
| Reimbursement rates | USDA + state amendments | Manual entry after USDA publishes | Before each fiscal year | State Finance |
| Organisation tax IDs | State business registration | File transfer | Weekly batch | State Secretary of State |
<!-- source: Application-to-Approval-Journey.md#external-sources -->

## What the legacy system actually does {#legacy-flow}

Traced from Iowa CTS VB.NET code-behinds and stored procedures. Useful because it shows the
real-world shape the greenfield design is compressing.

The legacy journey is **two distinct phases with a hard handoff**, not one continuous flow:

| Phase | Actor | Purpose |
|---|---|---|
| 1. Pre-screening (`/PreScreen/*`) | Public/anonymous | Self-service eligibility triage, no login |
| 2. Staff triage | State agency specialist | Manually imports viable inquiries |
| 3. Potential Sponsor App | Specialist or applicant | Detailed program-specific pre-agreement application |
| 4. Sponsor/Customer creation | Specialist | Converts prospect → `Customer` with an Agreement Number |
| 5. Full Application Packet | Sponsor + Reviewer | The FNS-regulated packet, with sites, budgets, checklists |
| 6. Approval engine | Reviewer/Approver | State machine + ClaimLaws generation |
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#feature-overview -->

**Critically: eligibility (PreScreen) is not the same object as the application, which is not
the same object as the agreement.** Each phase has its own primary key and its own status-code
vocabulary — a direct implication for the greenfield traceability model.
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#feature-overview -->

### The legacy state machine {#legacy-states}

```
NOTSUBMITTED --submit--> PENDINGAPPROVAL
             --update--> (stays NOTSUBMITTED)
PENDINGAPPROVAL --preapproval_1--> PREAPPROVAL_1   (NSLP-only intermediate gate)
                --approved-------> APPROVED        [triggers ClaimLaws]
                --return---------> RETURNED
                --deny-----------> DENIED
                --withdraw-------> WITHDRAWN
(any) --resubmitrequired--> NOTSUBMITTED
```

**The legacy system therefore does have RETURNED and WITHDRAWN**, plus an NSLP-only
`PREAPPROVAL_1` intermediate gate — which is what a "two-stage approval" looks like in
practice.
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#stage-5 -->

`approved` is the only button action that does not call the process procedure directly — it
redirects to a separate page and pipeline, because approval also has to run ClaimLaws
generation, which is long-running.
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#stage-5 -->

### Legacy behaviours worth carrying forward or deliberately dropping {#legacy-behaviours}

- ClaimLaws creation **loops per site** with a `runAppLaws` flag set only on the last site
  iteration — sponsor-level law creation depends on site-level laws completing first. **A
  sequencing dependency, not parallelizable.**
- Guarded by a `ClaimsLawStartYear` default: years before it are skipped entirely with **no
  laws created — a silent no-op that could mask a real problem.**
- `OriginalApprovedDate` is preserved on re-approval after a return/resubmit, so "first
  approved" history is not reset — **but computed differently for GLBL vs non-GLBL programs.**
- A compliance Review is conditionally spawned on approval, but only on first-ever approval and
  only if a flag encoded as **`SUBSTRING(ComplianceOpts, 19, 1) = 'Y'`** is set —
  magic-position substring flag encoding, easy to break silently.
- NSLP approval fires a **cross-program side effect** (`ApplicationPacket_CrossProcess_NSLPCACF`).
- `Customer.SSFO = Customer.NSLP` on creation — **direct object aliasing**, flagged in the
  source as a risk.
- The PreScreen → PotentialSponsor import **remaps ~50 answer codes into typed Y/N/X columns
  through CASE statements — code-driven, not data-driven.**
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#stage-5 -->
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#stage-6 -->
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#stage-4 -->
<!-- source: Iowa-CTS-Legacy-Application-to-Approval-Analysis.md#stage-2 -->

## Annual program year rollover {#rollover}

Not in Phase 1 scope (the job is registered but not required to fire), but designed.
<!-- source: CSN-Prototype-140826-133159.md#page-4 -->

Rather than making sponsors start from scratch, the system pre-populates a renewal with the
prior year's data — sites, menus, claim history — and asks the sponsor to confirm it is still
accurate, complete a checklist, and have an authorized director attest.

```
AutoGenerated (Hangfire) → Checklist → Attestation → StateReview → Approved
```

The data model is the same as a new application (`SponsorApplications`, `ProgramGroupYears`)
but the workflow is shorter and **the initial state is system-generated rather than
user-initiated.** A scheduled Hangfire job is the only thing that creates AutoGenerated
renewal records — **sponsors cannot initiate a rollover themselves.**
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-3 -->

Four tables: `PYRolloverJobs` (one row per tenant per cycle, with `SponsorsProcessed` /
`SponsorsErrored` for monitoring and retry), `PYRolloverSponsors` (one per sponsor, so the
state can filter by who has not completed attestation), `RenewalChecklists` (pre-populated
items — verify site list, confirm FSMC contract, update meal prices), `RenewalAttestations`
(electronic signature, **immutable once created**, capturing attestant, title, timestamp, IP
address and the legal attestation text).
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-4 -->
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-5 -->

**Bulk approval:** states with hundreds of sponsors do not individually review every routine
renewal. A state admin can select all renewals with no changed data, no open compliance
findings and no NDL concerns and approve them in one action — but **bulk approval writes
individual Approved transitions for each**, so the workflow log preserves the audit trail even
for bulk operations.
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-5 -->

**SFSP renews on a different cycle** — applications typically open February–April for the
coming summer, using the same workflow and tables but a different schedule, generating a
SchoolYear like "Summer2027". An `IsSFSP` flag on the rollover job distinguishes the cycles.
<!-- source: CSN-CNP Business Flow Gaps-140826-133122.md#page-5 -->

> The rollover job's firing date is stated three different ways in one document. See
> `99-contradictions-and-open-questions.md#rollover-date`.

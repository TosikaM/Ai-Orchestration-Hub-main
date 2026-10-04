# The Application-to-Approval Journey

# Part 1: The Main Journey, Stage by Stage

Think of this as the story of one sponsor (say, a school district or a daycare center) trying to get approved to run a federal nutrition program. This walkthrough follows the journey the way you'd actually experience it clicking through the screens — no code, no table names unless they help you recognize something on screen.

---

## The Cast of Characters

- **The Sponsor** — the organization applying (a school, a daycare, a summer camp operator)
- **The Caseworker** — state agency staff who helps applicants and does first-pass checks
- **The Reviewer** — state agency staff who does the formal review and can approve/deny
- **The State Agency Admin** — oversees the whole process, can configure things
- **The System** — runs background checks and enforcement automatically, no human needed

---

## Stage 1: "I'm interested, am I even eligible?" (Prospect)

Before anyone fills out a real application, some states let a prospective sponsor register interest first — almost like a "waiting room." This is called the **Prospect** stage.

**What the user sees:** A simple starting point where basic info is captured — who they are, what program they're interested in (school lunch, daycare food program, summer meals, etc.)

**Important thing to know as a tester:** This stage **doesn't exist in every state**. Some states go straight to a real application (Draft). Whether Prospect shows up or not is a setting per state, not a bug — so if you're testing State A and see this screen, but State B skips straight to the application form, that's expected behavior, not an inconsistency to log.

---

## Stage 2: Filling Out the Application (Draft)

Once past the interest stage, the sponsor is now filling out the actual application — the real form with real legal weight. This is the **Draft** status.

**What the user sees:** A multi-part application form. They can save and come back. Nothing is "official" yet — it's like a Word document they're still editing.

**What they need before they can move forward:** The system requires certain documents to be attached before you're allowed to submit — for example, a signed agreement and a policy statement about free/reduced meal pricing. These aren't optional extras; they're required by federal rule, so **no state can turn this requirement off**, no matter what.

**As a tester, this means:**
- Try clicking "Submit" without attaching the required documents → it should be blocked, with a clear message telling the applicant what's missing.
- This blocking behavior should be identical in every single state you test — if you find a state where you can submit without the documents, that's a real bug, because this rule is federally locked.

---

## Stage 3: "I hit Submit" (Submitted)

Once the required documents are attached and the sponsor clicks Submit, the application moves to **Submitted**.

**What happens the moment they click Submit:** The system quietly records an entry in the background saying "this application was submitted, by this person, at this time" — this is for the audit trail. As a user you won't see this directly, but if you ever need to prove *when* something happened, this is where that answer comes from.

---

## Stage 4: Someone Picks It Up for Review (UnderReview)

A Reviewer at the state agency picks up the application, and it moves to **UnderReview**.

**What the user sees (Reviewer's perspective):** A queue of applications waiting to be reviewed, assigned to them. They open it up and go through everything the sponsor submitted.

**Behind the scenes, something important happens automatically:** the system runs a background check against a federal "do not do business with" list (the National Disqualified List, or NDL) — checking the organization's name, tax ID, and the names of key people listed (like the director). This isn't something the Reviewer manually triggers; it happens as part of the approval attempt.

---

## Stage 5: The Approval Decision (Approved or Declined)

This is the moment of truth. The Reviewer clicks either **Approve** or **Deny**.

### If they click Deny:
Straightforward — the application moves to **Declined**, and that's recorded permanently.

### If they click Approve — here's where it gets interesting:

The system checks that background list result before actually letting the approval go through:

1. **Clean result ("No Match")** → Approval goes through immediately, no extra steps.

2. **Possible match found** → The system does **not** auto-block, but it also doesn't let the Reviewer just click through. It requires a **human to investigate** — someone has to look at the possible match, write a justification, and decide "yes this is really them, don't approve" or "no this is a false alarm, safe to approve." As a tester: try approving an application flagged as a possible match *without* completing this review step — it should refuse to let you approve until someone has recorded a decision.

3. **Confirmed match** → This is a hard stop. **No one — not the Reviewer, not a supervisor, not an admin — can override this.** If your test data has a confirmed match and you're somehow able to approve it anyway, that is a critical bug, because this is meant to be an absolute, unbreakable block by design.

**What the user sees either way:** A record is kept of this background check every single time an approval is attempted — even if it comes back clean. So even a "boring, nothing happened" approval leaves a trail showing the check was actually run.

---

## Stage 6: What Happens the Instant Approval Succeeds

The moment "Approve" actually goes through (not just clicked, but successfully completed):

- **A permanent snapshot is taken** of exactly what the application looked like at that moment — like a photograph, frozen in time. Even if someone edits related data later, this snapshot never changes. This matters because months or years later, if a federal auditor asks "what did this application look like the day it was approved?", the system has to answer that instantly, not by manually reconstructing old records.
- **The claim eligibility rules get "locked in"** for this sponsor going forward (this is what unlocks their ability to actually start submitting meal claims for reimbursement). Once this locks in, **it cannot be edited or undone** through the normal screens — there's no "Edit" button for it. If a mistake is found afterward, it has to be handled as a new correction process, not a quiet fix to the old record.

**As a tester, a good check here:** try to find any screen or action that lets you edit this locked-in record after approval. You shouldn't be able to — if you can, that's a significant finding.

---

## Things That Change by State (and why that's not a bug)

Different states are allowed to customize *some* parts of this journey, but never the core federal rules. A simple way to tell them apart when you're testing:

- **🔒 Locked / Federal** — every state behaves identically, no exceptions, no configuration screen even shows an edit option. Example: the required documents before submission, the Deny/Approve decision itself, the background check.
- **🔧 Configurable** — states can turn it on/off or tweak it. Example: whether the "Prospect" waiting-room stage exists at all, or one state adding an extra required document on top of the federal ones.

If you ever see a "locked" behavior differ between states, or a state successfully bypass it — that's the kind of bug worth escalating immediately, because it likely means a federal compliance rule got broken, not just a cosmetic inconsistency.

Also: whenever a state does customize something, the system requires whoever made that change to type a **real explanation of why** (at least 20 characters — so "N/A" or "asked to" won't count). That explanation gets saved permanently and can't be deleted, even if the change itself is later undone. Worth testing that you can't sneak past this by typing junk characters just to hit the 20-character minimum.

---

# Part 2: What Happens When Things Don't Go Smoothly (Denial & Appeal Path)

## The Straightforward Case: Denial

If the Reviewer decides to click **Deny** instead of Approve, the application moves to **Declined**. This is meant to be a clean, final decision — recorded permanently, no ambiguity.

## The "I Want to Challenge This" Path: Appeal

Here's something important to understand as a tester: **a Declined application is not necessarily the end of the story.** The sponsor has the right to challenge that decision, and there's a separate process just for that:

**Filed → Informal Resolution → Formal Hearing → Decision Issued → Closed**

Think of this as a completely separate case file that gets opened *about* the denied application, rather than the application itself changing. The sponsor files the appeal, there's an attempt to resolve it informally first, and if that doesn't work, it escalates to a formal hearing. At the end, a decision gets issued.

**Here's the part that matters most for testing:** if the appeal decision goes in the sponsor's favor, **the original Declined application can flip back — it gets reinstated**, essentially undoing the denial. This is a designed, deliberate reversal — not a bug, not a workaround.

**As a tester, this means:**
- Test that a Declined application really can be reinstated when an appeal is decided in the sponsor's favor — and that once reinstated, it picks back up appropriately (does it go to Approved directly, or back to UnderReview for a fresh look? — worth confirming with the team, the documentation doesn't spell out exactly which status it lands in).
- Test that an appeal decided *against* the sponsor leaves the application Declined, with no unexpected side effects.
- Check that the appeal process itself is fully separate and traceable — you should be able to look at the application's history and clearly see "this was Declined, then an appeal was filed, then it was reinstated" as a sequence of distinct events, not something that overwrites the original decision silently.

## An Honest Gap: "Send It Back for Fixes"

In a lot of everyday application systems, a Reviewer might want a lighter-weight option than Deny — something like "this is missing a signature, please fix and resend" without going through a full denial + appeal. I looked specifically for this ("Return for corrections," "Withdraw," "Resubmit") in the platform's design documentation, and **I could not confirm a documented version of this for applications specifically.** There is a similar concept for claims (a rejected claim can go back to "Submitted" once errors are fixed), but the application workflow docs only show Draft → Submitted → UnderReview → Approved/Declined, plus the separate Appeal process.

**This is worth a direct question to your team, not an assumption on my part** — is there a lighter "send back for corrections" step planned for applications, or is Deny + Appeal genuinely the only path once an application is submitted? I don't want to hand you a test case for a screen that may not exist.

---

# Part 3: Configuration, State Data, and Behind-the-Scenes Magic

## What Controls "How This Journey Works" — Configuration vs. Code

This journey isn't hardcoded. Different states can customize *some* parts (which stages show up, what documents are required, how many reviewers sign off). This happens through **Configuration**, not code changes.

### Configuration Layers

**Federal (Locked — Every State Identical)**
- Required documents before submission ✅ (locked, no state variation)
- NDL background check before approval ✅ (locked)
- Immutable approval snapshots ✅ (locked)
- Reimbursement rate freeze on approval ✅ (locked)

**State-Level (Configurable)**
- Whether a "Prospect" waiting room exists → on/off per state
- Additional state-specific required documents (e.g., Iowa requires a specific form) → added on top of federal ones
- Number of reviewers in approval chain → Iowa may require two-stage (caseworker + reviewer), another state might only need one
- Address field editability post-approval → depends on whether that state owns the address data or it comes from an external source

**Per-Sponsor (Customisable)**
- Operating months (Sept-May vs. year-round) → captured per school district
- Meal services offered (breakfast only vs. lunch + breakfast) → per school site
- Contact information → per organisation

### Example: Configuration in Action

**Scenario:** A Reviewer in Iowa tries to approve an application.

1. System loads Iowa's configuration → sees `REQUIRE_TWO_STAGE_APPROVAL = TRUE`
2. Check passes: this Reviewer has the authority to make final approvals ✅
3. System loads Iowa's configuration → sees `ADDRESS_SOURCE = "STATE_EIS"` (external state system owns addresses)
4. Fields marked as "read-only" because state owns them ✅
5. Application is approved → system generates claim-eligibility data based on Iowa's rules for meal types, reimbursement rates, etc. ✅

**If a different state's config said** `REQUIRE_TWO_STAGE_APPROVAL = FALSE` and `ADDRESS_SOURCE = "SPONSOR_ENTERED"`:
- Same application flow, but: one approval stage instead of two, address field is editable by sponsor ✅

**The key:** The same code runs everywhere; configuration changes behaviour.

---

## State Data Sources — "Where Does This Information Really Come From?"

Some fields in this journey aren't entered by the sponsor or reviewer — they come from **external state systems**. Understanding where data comes from is crucial for knowing what's a bug and what's "that field is read-only because it's managed elsewhere."

### Common State Data Sources

| Data | Source System | Mechanism | Freshness | Who Corrects It |
|------|---|---|---|---|
| **Addresses** (Iowa example) | Iowa's Enterprise Information System (EIS) | Database synonym / linked read | Nightly refresh | State EIS team |
| **County Codes** | State reference database | API call | On-demand | State GIS/Admin |
| **Reimbursement Rates** | USDA + state amendments | Manual entry (after USDA publishes) | Before each fiscal year | State Finance |
| **Organisation Tax IDs** | State business registration | File transfer | Weekly batch | State Secretary of State |

### What This Means for Testing

**Red Flag Questions:**
- You see an address field and think "that should be editable" → check first whether it's a state-managed field. If it is, read-only is correct, not a bug.
- You see a reimbursement rate and wonder why you can't edit it → check whether it's locked because approval already happened, or because only state admins can edit rates, or both.
- You see data that looks stale → check when it was last refreshed from the source system. If it's a nightly refresh and you're looking at data from 30 hours ago, that's expected, not a bug.

**Good Test Case:**
- Identify one external state data source (e.g., addresses from Iowa EIS)
- Make a change in the source system
- Wait for the refresh (or trigger it manually if possible)
- Confirm the change appears in the application

---

# Part 3: QA Test Case Checklist (Plain-Language, No Code Needed)

Use this as a walk-through script. Each box is something you should be able to physically click through and verify on screen.

### ✅ Stage 1 — Prospect (if this state exists for your test state)
- [ ] Confirm whether your assigned test state shows a "Prospect" step at all. If it does, note it; if it doesn't, that's expected — don't log it as a bug.
- [ ] If Prospect exists, verify basic info (organization name, program of interest) is captured before moving to the real application.

### ✅ Stage 2 — Draft (Filling Out the Application)
- [ ] Start a new application and confirm you can save partial progress and come back later.
- [ ] Try clicking Submit with **no documents attached** → should be blocked, with a message telling you what's missing.
- [ ] Try clicking Submit with **only one of the two required documents** attached → should still be blocked.
- [ ] Attach both required documents (signed agreement + free/reduced price policy statement), then Submit → should succeed.
- [ ] Repeat the "missing documents blocks submission" check in at least two different states → confirm it behaves identically in both (this rule should never differ by state).

### ✅ Stage 3 — Submitted
- [ ] After clicking Submit, confirm the application's status visibly changes to "Submitted" on screen.
- [ ] Check that a history/audit view (if visible to your role) shows a timestamped "submitted" event.

### ✅ Stage 4 — UnderReview
- [ ] As a Reviewer, confirm the submitted application appears in your review queue.
- [ ] Open the application and confirm you can see everything the sponsor submitted, including attached documents.

### ✅ Stage 5 — Approval Decision
- [ ] With a "clean" test sponsor (no NDL match), click Approve → should succeed immediately.
- [ ] With a test sponsor set up to trigger a **"possible match"** result, try to Approve *without* completing the required investigation step → should be blocked.
- [ ] Complete the investigation with a decision of "safe to approve" → then try Approve again → should now succeed.
- [ ] Complete the investigation with a decision of "this is really them" (denied override) → try Approve again → should remain blocked.
- [ ] With a test sponsor set up to trigger a **"confirmed match"** → try every way you can think of to approve it (different roles, different screens) → it should be blocked in every single case, with no override option anywhere.
- [ ] Click Deny on a clean application → confirm it moves to Declined and stays there.

### ✅ Stage 6 — After Approval
- [ ] After a successful approval, look for any "Edit" option on the now-locked claim eligibility data → confirm there isn't one.
- [ ] Confirm you (or someone with appropriate access) can pull up "what did this application look like at the moment it was approved" and get a clear, complete answer — not a "reconstruct it manually" situation.
- [ ] Confirm the approved sponsor can now do the next real-world thing this unlocks (e.g., start submitting a claim) — this is the practical proof that "locked in" actually took effect.

### ✅ Denial & Appeal
- [ ] Deny a test application, then file an appeal against it.
- [ ] Push the appeal to a decision in the sponsor's favor → confirm the application status changes appropriately (reinstated) and this shows clearly in its history.
- [ ] Push a separate appeal to a decision against the sponsor → confirm the application stays Declined with no unexpected changes.

### ✅ State-by-State Behavior Checks
- [ ] Pick one "locked/federal" rule (like required documents before submission) and test it in at least 2–3 different states → it must behave identically everywhere.
- [ ] Pick one "configurable" behavior your team has confirmed exists (e.g., an extra state-specific required document) → confirm it only applies in that one state, and doesn't leak into others.
- [ ] If you have access to see how a state-specific change was made, confirm there's a written explanation of at least 20 characters attached to it, and that it can't be deleted later.

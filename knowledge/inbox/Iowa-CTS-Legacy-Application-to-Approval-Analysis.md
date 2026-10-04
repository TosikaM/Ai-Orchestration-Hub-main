# Application-to-Approval Workflow — Iowa CNP Legacy System (CTS) Analysis

I've traced the actual code paths (VB.NET code-behinds + SQL stored procedures) rather than inferring from UI alone. Here's the reverse-engineered journey.

## Feature Overview

This legacy system implements the application-to-approval journey in **two distinct phases with a hard handoff**, not one continuous flow:

| Phase | System Area | Actor | Purpose |
|---|---|---|---|
| 1. Pre-Screening | `/PreScreen/*` | Public/anonymous applicant | Self-service eligibility triage (no login) |
| 2. Staff Triage | `/PreScreen/PreScreenApplicationList.aspx` | State agency specialist | Manually imports viable inquiries |
| 3. Potential Sponsor App | `/PotentialSponsor/*` | Specialist (assisted) or applicant | Detailed program-specific pre-agreement application |
| 4. Sponsor/Customer Creation | `PotentialSponsorCreate.aspx` | Specialist | Converts prospect → `Customer` entity with Agreement Number |
| 5. Full Application Packet | `/Nslp,Sfsp,Cacf,Dch/AppPacket.aspx` | Sponsor + Reviewer | The actual FNS-regulated application packet, with sites, budgets, checklists |
| 6. Approval Engine | `Common/AppPacketProcess.aspx` + SQL procs | Reviewer/Approver | State machine + ClaimLaws generation |

Critically — **eligibility ("PreScreen") is not the same object as the application, which is not the same object as the agreement.** Each phase has its own primary key and its own status code vocabulary. This has direct implications for your Greenfield RF traceability model.

---

## Data Flow & State Mapping

### Stage 1 — Public PreScreen (no auth)
`PreScreenOverview` → `PreScreenQuestionGroup` → `PreScreenQuestion` (recursive, stack-based navigation via `Session("PreScreenQuestionStack")`) → `PreScreenContact` → `PreScreenSummary`

- Answers held **only in session** (`PreScreenSharedData.CustomerAnswers` dictionary) until final submit — nothing persists to DB until `PreScreenSummary.Page_Load`.
- On submit: `PreScreenContacts` saved → `PreScreenApplications` row created (`StatusCode = 'STATUS_CODE_PRESCREEN_PENDING'`) → deterministic `ReferenceNumber` generated (`yyyyMMdd` + 3 letters of name + `ApplicationID mod 1000`) → answers written to `PreScreenCustomerAnswers` → **eligibility computed in code-behind** (hardcoded business rules, state-specific branches for IA/WV/PA/SD/NC) → confirmation email sent.
- Ineligible branch: `PreScreenNotEligible.aspx` (dead end, no application created downstream).

### Stage 2 — Staff Import (bridge from anonymous to authenticated system)
`PreScreenApplicationList.aspx` (internal staff grid) → specialist selects rows → `btnImportPopup_Import_Click` → calls **`PotentialSponsorApplication_Import`** stored proc.

This proc:
- Creates `PotentialSponsorApplications` + `PotentialSponsorContacts` (+ Board/Principal contacts for some states)
- **Remaps ~50 PreScreen answer codes into typed Ind (Y/N/X) columns** on `PotentialSponsorApplicationCACFDetails` / `NSLPDetails` / `SFSPDetails` — this mapping is entirely code-driven (CASE statements), not data-driven
- Sets `PreScreenApplications.StatusCode = 'STATUS_CODE_PRESCREEN_IMPORTED'` and links `PotentialSponsorApplicationID` back
- Assigns a `SpecialistAssignedID`

**A Potential Sponsor Application can also be created directly** (bypassing PreScreen entirely) via `PreScreenApplicationList → btnAddPopup_Add_Click`, landing on `PotentialSponsorApplication_{CACF|NSLP|SFSP}.aspx?PotentialSponsorApplicationID=0`.

### Stage 3 — Potential Sponsor Application
Program-specific detail forms (`PotentialSponsorApplication_NSLP/SFSP/CACF.aspx`) → hub page `PotentialSponsorApplicationPacket.aspx` (notes, documents, contacts, agreement number).

### Stage 4 — Customer/Agreement Creation
`PotentialSponsorCreate.aspx.btnAdd_Click`:
1. Generates next `AgreementNbr` via `fn_GetCustomerAgreementNbr_Next()`
2. Creates `Customers` row (`StatusCode = 'ACTIVE'`)
3. **Copies program-participation flags** from the Potential Sponsor App's `ProgramGroupCode`/`SponsorTypeCode` into `Customer.NSLP/SFSP/CACF/DCH/CMDT`, each defaulted to `ClaimLevelCode = 'SPONSOR'`, `DataEntryMethod = 'ELECTRONIC'`
4. `Customer.SSFO = Customer.NSLP` (direct object aliasing — worth flagging, see risks)
5. Back-links `PotentialSponsorApplications.CustomerID`

*Alternative path:* specialist can match to an **existing** `CustomerID` instead of creating new (`gvList_RowCommand`) — i.e., an existing sponsor applying for an additional program.

### Stage 5 — Full Application Packet & State Machine
This is the actual FNS-regulated packet, tracked at `ProgramEnrollments`/`ProgramGroupEnrollments` level (`ap_ProgramEnrollmentLevel` decides which table per `CnpDefaults`).

Button actions (`AppPacketTools.ap_PageNav`) map to `PacketProcessCode` values consumed by program-specific procs (`ApplicationPacket_Process_NSLP/SFSP/CACF/DCH/GLBL`):

```
NOTSUBMITTED
   --submit--------------> SUBMITPACKET  -> PENDINGAPPROVAL
   --update---------------> UPDATEPACKET  -> (stays NOTSUBMITTED)
PENDINGAPPROVAL
   --preapproval_1--------> PREAPPROVAL_1  (NSLP-only intermediate gate)
   --approved-------------> APPROVEPACKET  -> APPROVED   [triggers ClaimLaws]
   --return---------------> RETURNPACKET   -> RETURNED
   --deny-----------------> DENYPACKET     -> DENIED
   --withdraw-------------> WITHDRAWPACKET -> WITHDRAWN
(any) --resubmitrequired--> RESUBMITREQUIRED -> NOTSUBMITTED
```

Note the `"approved"` case is the **only** button action that doesn't call `ap_ProcessPacket` directly — it redirects to `Common/AppPacketProcess.aspx?PacketProcessCode=APPROVEPACKET`, a *separate* page/pipeline, because approval also has to run ClaimLaws generation (long-running, uses a JS progress bar + server-side `Response.Write` streaming).

### Stage 6 — Approval Post-Processing (`AppPacketProcess.aspx` → `AppPacketTools`/SQL)
1. `_AppPacketTools.ap_ProcessPacket("APPROVEPACKET")` — runs the program's validation gate stored proc **first**. If `RtnCde <> 0`, processing stops (error surfaced, packet NOT approved).
2. If gate passes → `CreateLaws()`:
   - Branches by `ProgramGroupCode` to `CreateLawsForNSLP` / `CreateLawsForSFSP` / `CreateLawsForThisSponsor` (CACF) / `CreateDchSponsorLawsOnly` / `CreateLawsForThisSponsorGLBL`
   - For NSLP/SFSP: fetches all sites needing law records, loops calling `SiteApplicationClaimLaws_Create` / `SiteApplicationSFSPClaimLaws_Create` per site, tracking a `runAppLaws` flag (only `'Y'` on the *last* site iteration — meaning sponsor-level law creation depends on site-level laws completing first — **sequencing dependency**, not parallelizable)
   - Guarded by `ClaimsLawStartYear` CnpDefault — years before this are skipped entirely (no laws created), a **silent no-op** that could mask a real problem
3. `MarkPacketApproved()` → `ApplicationPacket_ApproveProcess` proc:
   - Sets `StatusCode='APPROVED'`, `CanClaim='Y'`, `PacketLockedToCustomer='N'`, `ApprovedBy`, `ApprovedDate`
   - Preserves `OriginalApprovedDate` if one already existed (re-approval after a return/resubmit doesn't reset "first approved" history) — **but computed differently for GLBL vs. non-GLBL** (CASE-preserve vs. direct COALESCE at select time)
   - Clears `SubmitTicketedDate`/`ScheduledReviewDate` ("place in line" queue is released on approval)
   - Logs to `ProgramEnrollmentEvents`/`ProgramGroupEnrollmentEvents` (`PACKET_APPROVED`, and `PACKET_SUBMITTED` retroactively logged if coming from GLBL)
   - Conditionally spawns a **compliance Review** (`ApplicationPacket_Process_CreateReview`) — but *only* if `OriginalApprovedDate IS NULL` (first-ever approval) and a `CnpDefaults.ComplianceOpts` flag (`SUBSTRING(...,19,1)='Y'`) is set — magic-position substring flag encoding, easy to break silently
   - For NSLP specifically: fires `ApplicationPacket_CrossProcess_NSLPCACF` — cross-program side effect on approval

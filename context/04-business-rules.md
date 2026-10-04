<!-- PROJECT CONTEXT — synthesised, not a source document.

     Every factual claim here needs a provenance comment naming where it came from:
         <!-- from: knowledge/distilled/<topic>.md#<anchor> -->
     `python scripts/project-context.py check` fails on a claim without one.

     If a statement has no source, it is an ASSUMPTION. Move it to 06-open-questions.md
     with the assumption stated, rather than leaving it here where the next reader will
     take it for a requirement. -->

# Business rules

Rules the software must enforce. **Federal rules are marked 🔒 — they are enforced in code and
cannot be reached through any configuration surface.** Everything else is configurable within
stated bounds.

## The federal guardrail {#federal-guardrail}

**🔒 `IsFederal = true` is a structural lock with no override mechanism.** When set, no tenant
override is accepted; the API returns HTTP 403 with a federal citation.
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#decision -->

It applies at six surfaces: config values (`ConfigDefinitions`), workflow states, workflow
transition conditions and actions, permission catalog entries, role-permission pairs, and
validation error severities.
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#decision -->

**Enforcement is layered, and the layers are not equivalent** — this distinction must survive
into implementation:

- **UI suppression is a usability feature, not security.** Federal controls are hidden before
  any API call, but that is not the control.
- **The API guardrail only fires when the write passes through the API.** Direct SQL, a data-fix
  migration or a CI/CD script bypasses it entirely.
- **The database triggers are the last line of defence** and fire for every write regardless of
  source. `trg_block_federal_transition_override` and `trg_block_federal_config_override`, both
  `BEFORE INSERT OR UPDATE`.
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#layers -->

**🔒 Never disable these triggers.** Any migration that DROPs, DISABLEs or modifies either must
be blocked at review, and trigger integrity verified after every migration touching the override
tables.
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#layers -->

**🔒 Every blocked attempt is audited even though the write rolls back.**
`log_federal_guardrail_violation()` writes to `AuditLogs` in an **autonomous transaction**, so
the rollback does not erase the record. Row carries `EntityType = 'FederalGuardrailViolation'`,
the source role, target table, rejected values and timestamp.
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#layers -->

**🔒 The flag itself is not configurable.** Set at deployment, changed only by versioned
migration reviewed by a senior engineer, never exposed in any UI.
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#flag-is-not-configurable -->

**🔒 Belt and suspenders on bounds:** for federally locked numeric values, `MinValue` and
`MaxValue` both equal `DefaultValue`, making a different value arithmetically impossible even
for a user who somehow holds override permission.
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#bounds -->

## Identity and access {#access}

**🔒 There is no path where a fabricated identity token grants access** — including test and
demo builds.
<!-- from: knowledge/distilled/04-identity-and-rights.md#authentication -->

Four fail-safe rules, all of which fail *closed*:

- A stale session must be re-established through the real IdP; **no silent renewal.**
- **If the IdP is unreachable, nobody logs in.** There is no fallback auth path.
- A permission check that cannot complete due to a system error **denies**, never grants.
- A user with no assigned role or scope **sees no data** — never an error revealing internals,
  never a default of "see everything."
<!-- from: knowledge/distilled/04-identity-and-rights.md#authentication -->

**No screen, button or link being hidden is ever the security control.** Every action is
independently re-validated server-side before it is carried out. Data visibility is enforced at
the data-access layer, not by each screen filtering correctly.
<!-- from: knowledge/distilled/04-identity-and-rights.md#enforcement -->

**Explicit `Revoke` at any layer beats `Grant` at a lower layer.** A state can always lock
something down further than the platform default; it can never accidentally loosen a
restriction imposed deliberately at a broader level. `IsFederal` blocks revocation at all three
layers.
<!-- from: knowledge/distilled/04-identity-and-rights.md#override-layers -->

**The JWT carries roles and tenant scopes, never the permission list.** Permissions resolve
server-side on every action. Application code never parses JWT claims for authorization.
<!-- from: knowledge/distilled/04-identity-and-rights.md#token -->

**The token lives in service memory only** — never localStorage, never sessionStorage — so it
cannot be recovered after the browser closes.
<!-- from: knowledge/distilled/04-identity-and-rights.md#token -->

**A tenant-defined role cannot exceed the ceiling of the highest system role**, and its
`ScopeConstraint` can never be `CrossTenant`.
<!-- from: knowledge/distilled/04-identity-and-rights.md#tenant-roles -->

## Configuration {#configuration}

**Three layers, most specific wins, no blending:** tenant override → program default → platform
default. The platform default guarantees every key has a value, so no null reference is
possible.
<!-- from: knowledge/distilled/03-configuration-model.md#hierarchy -->

**Every value is typed and bounded.** An out-of-range or wrong-type value is rejected at save
time — never silently accepted and discovered later as a runtime failure.
<!-- from: knowledge/distilled/03-configuration-model.md#bounds -->

**Every override requires a stated reason and an effective date.** No setting changes
anonymously. A change can be scheduled for a future date with nobody present and nothing
deployed — future-dated rows sit harmlessly until their date arrives and simply become the
winning row in the COALESCE chain.
<!-- from: knowledge/distilled/03-configuration-model.md#tenant-overrides -->
<!-- from: knowledge/distilled/03-configuration-model.md#effective-dating -->

**Every change is logged — successful or not.** A rejected change never appears in what is
currently in effect, but every attempt still generates a compliance record.
<!-- from: knowledge/distilled/03-configuration-model.md#tenant-overrides -->

**`ICnpConfigService.GetValue<T>()` is the sole accessor.** Reading the config tables directly
is prohibited, so that resolution, bounds validation and caching are always applied — and so no
service hardcodes a default because it forgot to call the config layer.
<!-- from: knowledge/distilled/03-configuration-model.md#single-accessor -->

**Rate limits:** cache-bust is capped at 10 operations per admin per hour to prevent a
stampede, and repeated rapid changes to the same setting by the same admin are rate-limited.
<!-- from: knowledge/distilled/03-configuration-model.md#cache-bust -->

**A federal error cannot be downgraded to a warning.** The write service checks
`Errors.IsFederal` before accepting an `OverrideType = Warning`; description overrides remain
allowed.
<!-- from: knowledge/distilled/03-configuration-model.md#tenant-error-config -->

**Operational trap:** a Tier 3 (nightly) key changed at 2pm does not take effect until midnight
unless a manual cache bust is issued.
<!-- from: knowledge/distilled/03-configuration-model.md#cache -->

## Workflow {#workflow}

**Only valid, permitted next steps are ever presented.** A user sees only actions they are
permitted to take *and* that are valid for the current status — and nothing offered can fail
because it was an invalid state change. Unavailable actions are **hidden, not disabled.**
<!-- from: knowledge/distilled/02-workflow-engine.md#execution -->
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#sprint-6 -->

**A failed condition halts the process before any state change is written**, and **no partial
change is recorded as if it had succeeded.**
<!-- from: knowledge/distilled/02-workflow-engine.md#execution -->

**Actions are transactional.** The status change and its actions run in one transaction; if
`FreezeClaimLaws` fails, the status change rolls back and the application stays where it was.
<!-- from: knowledge/distilled/02-workflow-engine.md#execution -->

**Every review action is tied to a specific user.** There is no anonymous or system-attributed
review action.
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#determination -->

**An application in a final state does not silently reopen.** Revisiting a final determination
is a distinct, deliberate, traceable action — never an ordinary workflow step.
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#appeal -->

**A state's customization never alters the shared baseline** other states rely on. Tenant
variation lives only in `TenantTransitionOverrides` — **never state-keyed branches in code.**
<!-- from: knowledge/distilled/02-workflow-engine.md#override-types -->

**Every PS override write requires a justification of at least 20 characters**, stored
permanently in an autonomous transaction so it survives a rollback, and uneditable afterwards.
A blocked-phrase list ("N/A", "per request", "test") triggers a non-blocking warning.
<!-- from: knowledge/distilled/02-workflow-engine.md#ps-governance -->

**Named hooks, never an expression language.** Federal math must never be encoded in a
configuration string, because then it can be configured differently for a state. Adding a
condition requires both a data row *and* a code implementation — configuration is fast,
extending the hook library requires review.
<!-- from: knowledge/distilled/02-workflow-engine.md#named-hooks -->

**The Rules Engine can never block a transition.** Synchronous and transactional → named hook;
asynchronous and post-commit → Rules Engine. *"There are no exceptions."* A PR putting
assignment logic in a named hook, or a blocking condition in the Rules Engine, should be
rejected.
<!-- from: knowledge/distilled/02-workflow-engine.md#rules-engine-boundary -->

## Application submission {#submission}

**A sponsor sees only their own organization's applications**, regardless of what they click,
type into a URL, or call directly.
<!-- from: knowledge/distilled/04-identity-and-rights.md#scoping -->

**🔒 Required documents before submission** — a signed agreement and a free/reduced price policy
statement — are federal (7 CFR 210.9). **No state can turn the requirement off.** A state may
add documents on top; it cannot remove the federal ones.
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#draft -->

**In-progress work is preserved.** A sponsor who leaves partway through returns to intact,
editable data.
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#draft -->

**Submission requires completeness**, and the system identifies what is missing or invalid
before submission is allowed.
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#draft -->

**The rendered form always matches the state's current form definition** — it cannot silently
drift from what the state configured.
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#draft -->

**State-side override of a validation failure is permitted only where configuration explicitly
allows it** — and never for a federally locked condition.
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#draft -->

## NDL screening {#ndl}

**🔒 Screening runs on every single approval attempt.** Not optional, not skippable, and **a
previous pass does not exempt a later attempt.** It checks organization name, EIN and the names
of key principals.
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#ndl-mechanism -->

**🔒 Three outcomes, and only three:**

| Outcome | Behaviour |
|---|---|
| No Match | Approval may proceed |
| Possible Match | Neither auto-blocks nor auto-proceeds — routed to a designated reviewer for an explicit recorded decision |
| **Confirmed Match** | **Approval permanently blocked** |
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#ndl-outcomes -->

**🔒 A Confirmed Match is the strongest guarantee in the platform** — stronger than the general
permission-override model, because it cannot be reached through any override layer at all. The
hook returns false for a ConfirmedMatch **regardless of any `NdlOverrideRequest` outcome.**
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#ndl-outcomes -->

**🔒 Segregation of duties:** a reviewer who was also the one who submitted the application, in
any capacity, may not clear a Possible Match on it.
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#ndl-sod -->

**🔒 Every attempt is recorded regardless of outcome, with the specific match criteria** —
organization name, tax ID or named individual — not merely the fact that a match occurred.
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#ndl-recording -->

**A synthetic dataset is acceptable in Phase 1; treating a match against it differently from a
real match is not.**
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#ndl-phase-1 -->

## The approval freeze {#freeze}

**🔒 Approval automatically and immediately creates exactly one `ClaimLaws` record.** No
exceptions, no delay.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#immutability -->

**🔒 The snapshot is genuinely permanent.** It cannot be edited or deleted through any interface
or administrative capability. **There is no "correct a mistake" edit path** — a correction is a
new, separately recorded action. In Phase 1 this is testable: `ClaimLaws` has no UPDATE
endpoint and an attempt returns HTTP 405.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#immutability -->

**🔒 Later rule or rate changes never retroactively affect an existing frozen record.**
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#immutability -->

**🔒 The snapshot reflects the rules in force at the literal moment of approval** — not at
submission, not at review.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#immutability -->

**The displayed values must exactly match what was stored.** There is no separate display
version that could drift.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#immutability -->

**One generic mechanism serves every program**, driven by configuration — replacing what are
today multiple duplicated per-program procedures.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#immutability -->

## Federal math {#federal-math}

**🔒 CEP claiming percentage = ISP × 1.6, capped at 100%.** The multiplier is 42 U.S.C.
§ 1759a(a)(1)(F)(viii). *"Any attempt to make it configurable would constitute a federal
compliance violation."* ISP must be ≥ 40% to qualify.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#cep -->

**🔒 A revised claim always uses the rate for its original claim month**, not the rate current
at reprocessing time. A revised October 2024 claim processed in August 2025 uses the October
2024 rate.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#claimlaws-problem -->

**🔒 Rounding is `Math.Round(value, 4, MidpointRounding.AwayFromZero)` and MUST match legacy
exactly.** Characterization tests are required before any legacy stored procedure is retired.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#rounding -->

**🔒 CACFP day care homes: maximum two meals + one snack, or one meal + two snacks, per child
per day.** A child cannot be claimed for three full meals (7 CFR 226.20).
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#cacfp -->

**🔒 CACFP meals not meeting the meal pattern are disallowed even if the count is correct.**
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#cacfp -->

**🔒 FDCH Tier I certification windows are evidence-based and not configurable:** 60 months
where based on census tract or school eligibility, 12 months where based on provider income.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#cacfp -->

**🔒 SFSP: a 2% second-meal cap and a 50% attendance cap at some site types**; summer sites must
record actual attendance rather than projecting counts.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#summer -->

**🔒 The anomaly gate:** any rate change greater than 10% from the prior year is hard-blocked
for human verification against the official Federal Register document. USDA has issued
erroneous rate documents before.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#anomaly-gate -->

**Operational obligation, not just data entry:** rates for the new school year must exist
before any claim with a 1 July+ date can pass validation. The platform does not block
submission — the lookup returns null and the claim fails at processing time.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#rate-availability -->

**A new program year with no rates is valid.** Rollover and rate insertion are independent
operations; both must complete before claims can be processed.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#rate-availability -->

**FFVP has no ClaimLaws** — reimbursement equals actual expenditure, so there is no rate to
freeze.
<!-- from: knowledge/distilled/06-federal-math-and-claimlaws.md#ffvp -->

## Audit {#audit}

**🔒 There is no category of consequential action that is silently excluded.** The completeness
guarantee applies without exception to every business function; **none are permitted an audit
gap.**
<!-- from: knowledge/distilled/07-audit-and-immutability.md#completeness -->

**🔒 Failed and blocked actions produce audit records too** — a validation failure, a permission
denial, a compliance block — documenting the attempt and why it did not succeed.
<!-- from: knowledge/distilled/07-audit-and-immutability.md#completeness -->

**🔒 The trail is genuinely append-only.** No record can be edited or deleted by anyone through
any interface, including the most privileged administrative access. Correcting a mistake
elsewhere produces a *new* record.
<!-- from: knowledge/distilled/07-audit-and-immutability.md#completeness -->

**Before/after content reflects the actual affected data at that moment** — not reconstructed or
inferred after the fact.
<!-- from: knowledge/distilled/07-audit-and-immutability.md#completeness -->

**All audit writes go through `IAuditService`.** No direct table writes from application code.
Schema changes to audit tables add columns only.
<!-- from: knowledge/distilled/07-audit-and-immutability.md#iauditservice -->

**Viewing the audit trail requires specific authorization** — it is not open to every logged-in
user.
<!-- from: knowledge/distilled/07-audit-and-immutability.md#completeness -->

**The timeline is plain-language and chronological**, not raw log entries requiring
interpretation.
<!-- from: knowledge/distilled/07-audit-and-immutability.md#completeness -->

**Corrective action is an append-only dialogue** — neither reviewer nor sponsor can edit prior
entries, only append.
<!-- from: knowledge/distilled/07-audit-and-immutability.md#corrective-action -->

**Bulk approval writes individual transitions for each item**, so the audit trail survives bulk
operations.
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#rollover -->

## Data handling and delivery {#data-handling}

**🔒 No real program participant data exists anywhere in a non-production environment, under any
circumstance, for any reason including debugging.** Column masking is explicitly insufficient —
re-identification risk is high for small-population states.
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#test-data -->

**🔒 Offshore access to production is zero and structural** — enforced by IAM roles that
physically cannot reach production paths, not by policy.
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#offshore-rules -->

**🔒 Every PR touching compliance logic requires a US-based onshore approver.** Offshore
engineers cannot self-approve.
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#offshore-rules -->

**🔒 Changes to federal math require two-person review** — one onshore engineer plus one domain
expert — with an FNS regulatory reference in the PR description.
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#code-review -->

**No credentials in config files.** This is a PR-blocking finding. No secret value ever appears
in source, logs, container images or an application database.
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#credential-rules -->

**On suspected compromise, rotate immediately — service outage is accepted over continued
exposure.** But **on a confirmed incident, do NOT rotate or delete logs until forensics is
complete.** These two rules point opposite ways and both are correct; the second overrides the
first once an incident is confirmed, because rotating early destroys evidence needed for breach
notification compliance.
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#credential-rules -->
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#forensics -->

**`cnp_migration` is not a human credential.** It must not appear in any Secrets Manager path
accessible to engineers. *"If anyone requests this credential directly, that is an access
control violation."*
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#db-roles -->

**A structural change to the data model always goes through the tracked change process, even
for urgent fixes.**
<!-- from: knowledge/distilled/05-data-architecture.md#hard-requirements -->

**A qualified person formally signs off the demo environment — including confirming no real
data is present — before it is used in front of external stakeholders.**
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#sprint-8 -->

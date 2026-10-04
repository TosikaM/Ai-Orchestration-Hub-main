<!-- PROJECT CONTEXT — synthesised, not a source document.

     Every factual claim here needs a provenance comment naming where it came from:
         <!-- from: knowledge/distilled/<topic>.md#<anchor> -->
     `python scripts/project-context.py check` fails on a claim without one.

     If a statement has no source, it is an ASSUMPTION. Move it to 06-open-questions.md
     with the assumption stated, rather than leaving it here where the next reader will
     take it for a requirement. -->

# Overview

## What it is {#what-it-is}

A net-new platform for administering USDA Child Nutrition Programs on behalf of state
agencies, replacing two legacy LINQ product lines — CTS (22+ states, cloud) and DIS (6 states,
WinForms desktop) — with a single codebase serving all 28 states.
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#product -->

The distinguishing idea is a **hard boundary on configurability**: the platform is configurable
up to the edge of federal law, and everything mandated by federal regulation is implemented in
code and structurally protected so that no state, admin or script can change it. Engineering
calls this a *configurable federal nutrition compliance platform*; the "BPM + ERP" framing was
rejected for engineering use because an engineer building a true BPM engine to spec would
produce a system with no federal guardrails.
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#principles -->
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#naming -->

**Phase 1 — the October prototype** is one state's SNP application-to-approval workflow, end to
end, demonstrated live: real OIDC login, real database writes, a real workflow engine, and
federal compliance controls that actually block. Not mocked, not simulated for the demo.
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#phase-1 -->

The build is 16 weeks — 14 of active build plus 2 of freeze and demo prep — against an external
and fixed nTIG window.
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#shape -->

## Who uses it {#users}

| Role | What they do | Why they care |
|---|---|---|
| Sponsor Director / Staff | Completes and submits their organization's annual SNP application; manages sites and documents | Approval is what unlocks their ability to claim reimbursement for meals served |
| Caseworker | First-pass review; advances an application or returns it with a required explanation | They carry the volume; anything that makes review slower costs them their day |
| Reviewer | The formal approve/deny determination | They are personally attributable for every determination, permanently |
| State Agency Admin | State-wide oversight and configuration; assigns roles to state users | Accountable to USDA for the state's program integrity |
| LINQ Config Admin | Manages tenant-level program settings and workflow overrides across states | Their job exists because the alternative is a developer and a deployment |
<!-- from: knowledge/distilled/10-application-to-approval-flow.md#actors -->
<!-- from: knowledge/distilled/04-identity-and-rights.md#roles -->

Nine system roles exist in the full model; Phase 1 wires the five above.
<!-- from: knowledge/distilled/04-identity-and-rights.md#roles -->

Two audiences never touch the UI but shape the design: **FNS/FNA auditors**, who must be able
to reconstruct any past decision, and the **offshore delivery team**, whose access boundaries
are enforced structurally rather than by policy.
<!-- from: knowledge/distilled/07-audit-and-immutability.md#why-standalone -->
<!-- from: knowledge/distilled/08-security-and-offshore-governance.md#offshore-rules -->

## Success criteria {#success}

The prototype is demo-ready when twelve specific things are true, each with a named
verification method — including that the application list loads in under 2 seconds on the demo
environment, a config change propagates to the workflow in under 5 minutes, a Caseworker
calling a Reviewer-only endpoint gets HTTP 403 rather than merely a hidden link, all seven
IsFederal guardrail assertions pass in CI, and the environment runs 48 hours with zero ECS task
restarts.
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#dod-demo -->

Two of those carry the commercial argument rather than a technical one:

- **The speed demo** — an authorized admin changes a live setting and the change is visible in
  the workflow within 5 minutes, against a documented "legacy equivalent" story of how long the
  same change takes today.
<!-- from: knowledge/distilled/12-delivery-plan-and-gates.md#sprint-6 -->
- **The guardrail demo** — a federal value cannot be changed through any path, including a
  direct SQL write, and every blocked attempt is auditable.
<!-- from: knowledge/distilled/01-federal-guardrail-isfederal.md#layers -->

Beyond the demo, the platform-level success test is stated as a Definition of Done for each
phase: *the configuration team can accomplish everything in that phase's scope through the
Configuration API without a code change.*
<!-- from: knowledge/distilled/03-configuration-model.md#anti-pattern -->

## Explicitly out of scope {#out-of-scope}

**Out of scope for Phase 1**, and stated as deliberate deferral rather than gaps: claims
processing, reimbursement calculation, FNS report generation, live NDL integration, multi-state
operation, and every program other than SNP.
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#out-of-scope -->

The prototype **ends at application approval.** No claims, no FNS reports, no reimbursement
calculation beyond displaying the ClaimLaws freeze.
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#constraints -->

Also out: multi-state identity federation (the mechanism supports it; only one realm is wired),
multi-level approval chains beyond Caseworker → Reviewer, automated auto-approval without human
review, appeals following a denial, multi-region and DR infrastructure, and a full self-service
settings catalog.
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#business-functions -->

The Configuration Admin UI is **one screen for the speed demo**, not a full admin application.
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#constraints -->

Three areas are currently ambiguous rather than clearly in or out — site applications,
supporting-document upload, and the Returned state — and all three are recorded as blockers in
[06-open-questions.md](06-open-questions.md).

## The layering that decides where code goes {#layers}

The most recent document supplies a four-layer model that is the single most useful orientation
for a developer: **Foundation** (built once, knows nothing about any program or state) →
**Engines** (configurable, data-driven, no knowledge of any program or state) → **Domains**
(program-specific logic, plugging in through configuration rows and named hooks, never by
extending an engine) → **Verticals** (phase-specific slices).
<!-- from: knowledge/distilled/13-foundational-architecture.md#layers -->

Phase 1 builds the foundation **in full**, two of six engines, one domain (SNP) at minimum
scope, and one vertical.
<!-- from: knowledge/distilled/13-foundational-architecture.md#layers -->

The reason to hold this distinction in mind on every file: *"the team building Phase 1 always
knows whether the line of code they are about to write belongs in the foundation (and therefore
must be designed for Phase 2 and beyond) or in the vertical (and therefore can be optimised for
the prototype demo). That single distinction is the difference between a foundation that
survives Phase 2 and a foundation that has to be rebuilt."*
<!-- from: knowledge/distilled/13-foundational-architecture.md#layers -->

It also carries **ten foundation acceptance criteria** distinct from the demo-readiness list —
they prove the foundation is built, not just that the demo runs, and are stated as required for
Phase 2 to begin without rework. Three of them require provisioning a second state in Phase 1,
which the Prototype document forbids; see [06-open-questions.md](06-open-questions.md).
<!-- from: knowledge/distilled/13-foundational-architecture.md#acceptance -->

## How to read this context {#how-to-read}

`knowledge/` is the source of record: extracted client documents, and topic-level distillations
that cite them. `context/` is this synthesis. Every claim here points back to a distilled topic,
which points back to a page or slide in a client document.

**Where the sources disagree, this context does not choose.** The client's own rule is that a
design document beats a build plan and that conflicts are flagged rather than silently
resolved, so 39 recorded conflicts live in
`knowledge/distilled/99-contradictions-and-open-questions.md` and the build-affecting ones are
surfaced in [06-open-questions.md](06-open-questions.md).
<!-- from: knowledge/distilled/00-platform-and-phase-1-scope.md#precedence -->

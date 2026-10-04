# Identity, tenancy and the rights model

## Authentication {#authentication}

Users log in through a **real identity provider** using an industry-standard protocol. There
is no path in the product — including test and demo builds — where a fabricated identity
token grants access.
<!-- source: 01_FRD_Identity_Access.md#section-3 -->

Three business rules follow from that and are worth treating as acceptance criteria:

- A stale session must be re-established through the real IdP; there is no silent renewal that
  bypasses re-authentication.
- **If the identity provider is unreachable, nobody logs in.** There is no fallback auth path.
- A permission check that cannot be completed due to a system error results in access being
  **denied**, never granted by default.
- A user with no assigned role or scope sees no data — never an error revealing internals, and
  never a default of "see everything."
<!-- source: 01_FRD_Identity_Access.md#section-4 -->

> The choice of identity provider is the largest unresolved decision in this corpus — four
> different answers appear across the documents. See
> `99-contradictions-and-open-questions.md#auth-provider`.

## Tenant resolution {#tenant-resolution}

Each state agency reaches the platform on its own subdomain. The system determines which
state's data and rules apply from that address; a user never selects or declares their state.
<!-- source: 01_FRD_Identity_Access.md#section-3 -->

The chain: browser hits `<state>.linqcnp.com` → Route 53 → CloudFront → ALB → **YARP** extracts
the state code from the Host header → resolves the TenantId → **`ICnpContext`** simultaneously
resolves the `cnp_global` connection and that state's `cnp_ops` connection.
<!-- source: CSN-Frontend Architecture-140826-133148.md#page-2 -->

**The application selects the schema from the authenticated JWT, never from user input.**
<!-- source: CSN-Infrastructure Requirements-140826-133146.md#page-2 -->

Tenant context middleware sets the `cnp_app` `search_path` to `cnp_ops.{state_code}` per
request.
<!-- source: CSN-Prototype-140826-133159.md#page-11 -->

## The token carries roles, not permissions {#token}

The JWT carries the user's role assignments and tenant scopes so the application can bootstrap
the permission service without a database round-trip on every request. **It does not carry the
full permission list** — permissions are resolved server-side by `ICnpPermissionService` on
every action.

```json
{
  "sub": "usr-14422",
  "cnp_roles": [
    { "role": "Reviewer",   "tenant": "mn", "scope": "AllSponsors" },
    { "role": "Caseworker", "tenant": "ia", "scope": "AllSponsors", "domain": "SNP" }
  ],
  "cnp_tenants": ["mn","ia"],
  "cnp_cross_tenant": false,
  "exp": 1781300000
}
```

The broker validates authenticity (signature, expiry, issuer); the service resolves what those
roles carry for the requested tenant, applying all overrides. **Application code never parses
JWT claims directly for authorization decisions.**
<!-- source: CSN-CNP Rights-140826-132801.md#page-10 -->

The token lives in **service memory only** — never `localStorage`, never `sessionStorage` — so
it cannot be recovered after the browser closes or by inspecting saved site data. Re-login on
refresh is accepted for the prototype.
<!-- source: 01_FRD_Identity_Access.md#section-3 -->
<!-- source: CSN-Prototype-140826-133159.md#page-13 -->

## Why RBAC replaced the ACL {#rbac-decision}

The legacy system manages authorization through `CnpObjects` — an ACL with **5,082 permission
rows**, roughly 1,500 of them for report-level access. Every object has its own ACL entry;
adding an object requires a new row; auditing who can do what requires joins across multiple
tables and is rarely legible to non-engineers.

The replacement is a role-based catalog of approximately **180 `PermissionCatalog` entries**
organized by domain, **nine system roles**, role-permission assignments in `RolePermissions`,
per-state variation in `TenantRoleOverrides`.

The ~1,500 report-specific ACL rows collapse into domain-level permissions
(`REPORTING.FINANCIAL.READ`) — report access is governed by the domain the report covers, so
adding a report does not require a new permission row. Auditing "who has access to what"
becomes a single query across three tables, legible to a compliance auditor without
engineering assistance.

ABAC was considered and rejected as more expressive than needed, slower to evaluate and harder
to audit for nine roles.
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-7 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-8 -->

## Permission structure {#permission-structure}

Permissions are dotted keys: `SNP.Applications.Approve`, `CACFP.Claims.Submit`,
`Accounting.Reports.Export`. Each row carries `Domain`, `SubArea`, `Action`, `Description` and
`IsActive` (inactive permissions still exist for audit purposes but grant nothing).

The action vocabulary is fixed: **View, Create, Edit, Submit, Approve, Lock, Export, Configure,
Manage, Impersonate.**
<!-- source: CSN-CNP Rights-140826-132801.md#page-2 -->
<!-- source: CSN-CNP Rights-140826-132801.md#page-8 -->

## The nine system roles {#roles}

| Role | Can | Cannot | Scope |
|---|---|---|---|
| `StateAgencyAdmin` | Full access to all modules for their state; assign roles to state users; create tenant role overrides | Access another state's data | SingleTenant |
| `Reviewer` | View + approve applications and claims; initiate and conduct compliance reviews; calculate fiscal actions | Configure system settings | SingleTenant |
| `Caseworker` | Process applications and claims; view compliance records; run DC matching | Approve or lock records | SingleTenant |
| `SponsorDirector` | View/submit own sponsor's applications and claims; view compliance history; manage sponsor user accounts | — | SponsorOnly |
| `SponsorStaff` | Enter meal counts, submit claims; view own application status | Access financial data | SponsorOnly |
| `Finance` | Full Accounting domain; FNS report generation and export; grant balance management | Access program operational data | SingleTenant |
| `LINQConfigAdmin` | Manage CnpDefaults and workflow overrides; manage DC feed configs; operate across tenants | Access program operational data | CrossTenant |
| `FNSAuditor` | Read-only access to all records in assigned states; full audit trail and compliance history | Modify any record | CrossTenant (read-only), `ExpiresAt` always required |
| `LINQPlatformAdmin` | Full platform access including cross-tenant queries; view production data for support | — (LINQ internal only, never granted to state users) | CrossTenant, all actions logged with `CrossTenantFlag = true` |
<!-- source: CSN-CNP Rights-140826-132801.md#page-6 -->
<!-- source: CSN-CNP Rights-140826-132801.md#page-7 -->

Phase 1 wires **five demo roles**: Sponsor Director/Staff, Caseworker, Reviewer,
StateAgencyAdmin, LINQConfigAdmin. A user can hold more than one role.
<!-- source: 00_FRD_Index.md#section-4 -->
<!-- source: 01_FRD_Identity_Access.md#section-3 -->

## Three override layers, with a hard safety valve {#override-layers}

| Layer | What | Where |
|---|---|---|
| 1 — Role Permissions | The base set every role has by default across all states | `cnp_global` |
| 2 — Tenant Role Overrides | State-specific additions or removals from the base role | `cnp_ops` |
| 3 — User Permission Overrides | Individual grants or revocations; requires justification + expiry | `cnp_ops` |

Most specific wins — **except that an explicit `Revoke` at any layer beats a `Grant` at a
lower layer.** You cannot work around a revocation by granting at a lower layer.
<!-- source: CSN-CNP Rights-140826-132801.md#page-1 -->

This is the "layered, overridable role permissions with a hard safety valve" of FRD-01: a
state can always lock something down further than the platform default, but can never
accidentally loosen a restriction imposed deliberately at a broader level.
<!-- source: 01_FRD_Identity_Access.md#section-3 -->

`IsFederal` on a `RolePermissions` row blocks revocation at all three layers.
<!-- source: CSN-CNP Rights-140826-132801.md#page-1 -->

`UserPermissionOverrides` should carry an `ExpiresAt` — the document notes that individual
overrides without expiry dates *"accumulate into permission debt."*
<!-- source: CSN-CNP Rights-140826-132801.md#page-6 -->

## Tenant-defined roles {#tenant-roles}

Beyond overriding a system role, a tenant can define its own roles (`TenantRoleDefinitions` +
`TenantRolePermissions` in `cnp_ops`) — e.g. `SNP-Only-Caseworker`, `CACFP-Claims-View`. Two
guardrails:

- `TenantRoleDefinitions.ScopeConstraint` cannot be `CrossTenant` — that is reserved for
  system roles.
- A tenant-defined role **cannot exceed the ceiling of the highest system role**:
  `TenantRolePermissions` may only reference permissions the tenant's `StateAgencyAdmin` role
  already has.
<!-- source: CSN-CNP Rights-140826-132801.md#page-3 -->
<!-- source: CSN-CNP Rights-140826-132801.md#page-9 -->
<!-- source: CSN-CNP Rights-140826-132801.md#page-10 -->

`UserRoleAssignments` requires **exactly one** of `RoleId` or `TenantRoleId` to be non-null;
the engine rejects writes where both are null or both are set.
<!-- source: CSN-CNP Rights-140826-132801.md#page-6 -->

## Two scoping dimensions {#scoping}

**Sponsor scope** — `ScopeType` on `UserRoleAssignments`:

| ScopeType | Sees | Used by |
|---|---|---|
| `AllSponsors` | All sponsors in their assigned tenant(s) | StateAgencyAdmin, Reviewer, Caseworker, Finance |
| `SpecificSponsor` | Only the sponsor named by `SponsorId` | SponsorDirector, SponsorStaff |
| `OwnDataOnly` | Only records they personally created or are assigned to | Temporary reviewers, interns |

This replaces per-object ACL rows: one `ScopeType = SpecificSponsor` row enforces the boundary
for **every entity type in the system**, with no per-object permission management. The query
filter is injected automatically at the repository layer for all sponsor-scoped entities.
<!-- source: CSN-CNP Rights-140826-132801.md#page-10 -->
<!-- source: CSN-CNP Rights-140826-132801.md#page-11 -->

**Domain scope** — `DomainScope` on `UserRoleAssignments` answers "which programs can this
user operate in?" States with separate staff per program assign `Caseworker` with
`DomainScope = 'SNP'` to one group and `'CACFP'` to another. Null = all domains the role's
permissions cover.
<!-- source: CSN-CNP Rights-140826-132801.md#page-11 -->

## Enforcement, not decoration {#enforcement}

Two requirements make the enforcement position explicit, and both are testable:

- **No screen, button or link being hidden is ever the security control.** Every action is
  independently re-validated against current permissions on the server before it is carried
  out.
- **Data visibility is scoped automatically at the data-access layer**, not by convention in
  each screen — it does not depend on the application screen having been built correctly.
<!-- source: 01_FRD_Identity_Access.md#section-3 -->

`ICnpPermissionService` is the only interface application code uses for authorization; direct
role checks are prohibited. It is cached per-request, invalidated when a `UserRoleAssignment`
or `TenantRoleOverride` is written, and at midnight UTC for expiring assignments.
<!-- source: 51 Feature List.md#RF-07 -->
<!-- source: CSN-CNP Rights-140826-132801.md#page-8 -->
<!-- source: CSN-CNP Rights-140826-132801.md#page-9 -->

The Phase 1 acceptance test is concrete: a Caseworker token calling
`GET /applications/review-queue` must return HTTP 403 — not merely have the link hidden.
<!-- source: CSN-Prototype-140826-133159.md#page-17 -->

## Migrating the 5,082 ACL rows {#acl-migration}

A data exercise, not a code exercise, in six steps: AI-assisted catalog extraction with
onshore validation → role mapping → exception identification (users who do not map cleanly
become `TenantRoleOverrides` or `UserPermissionOverrides`) → tenant variation analysis →
**parallel validation in shadow mode alongside `CnpObjects` for one school-year cycle**, with
discrepancies investigated → cutover, old ACL rows retained read-only for audit.
<!-- source: CSN-CNP Rights-140826-132801.md#page-12 -->
<!-- source: CSN-CNP Rights-140826-132801.md#page-13 -->

**Phase 1 scope is the SECURITY domain only** — the smallest domain and the natural starting
point. CONFIGURATION follows, then the program domains in Phase 3 order (SNP → CACFP → SFSP).
Full migration is not required before Phase 1 launch; `CnpObjects` can coexist during the
transition.
<!-- source: CSN-CNP Rights-140826-132801.md#page-13 -->
<!-- source: CSN-Architecture Proposals-140826-132900.md#page-8 -->

The identified risk is worth carrying forward: 5,000+ ACL rows imply highly granular
permissions that evolved organically over years, and mapping them is **where access
regressions are most likely to hide** — either over-permissive or over-restrictive. The
mapping needs line-by-line verification against real production ACL data, and that
verification has to happen onshore because the offshore team cannot see production.
<!-- source: CSN-Data-140826-132933.md#page-49 -->

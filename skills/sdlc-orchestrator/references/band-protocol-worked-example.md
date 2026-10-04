# Reference: The Cross-Repo Band Protocol, Worked

> **Progressive disclosure.** Load this when a change actually crosses repositories.
> Most pipelines are single-repo and should not pay for this.

## The Requirement

> "Add an `ImpactInvestment` amount to the donation flow so it shows on the donation
> form, is stored, and appears in the quarterly report."

Four repositories, one requirement, and the order matters more than anything else here.

## Step 1 — Establish Execution Order

Dependency-first: **producers before consumers.**

```
shared-library  →  command-api  →  query-api  →  frontend
   (contract)      (writes it)     (reads it)    (shows it)
```

Get this backwards and the frontend compiles against a field the API has not shipped,
which passes CI in the frontend repository and fails in production.

## Step 2 — The Band File

`memory/sessions/pipe-m8x2k1.band.json`:

```json
{
  "requirement": "Add an ImpactInvestment amount to the donation flow",
  "executionOrder": ["shared-library", "command-api", "query-api", "frontend"],
  "completedRepos": [],
  "sharedContracts": {},
  "remainingRepos": ["shared-library", "command-api", "query-api", "frontend"],
  "pipelineState": "analyze"
}
```

## Step 3 — Repo 1, `shared-library`

Analyze, implement, verify. Then record what the repo **exposed**:

```json
{
  "repo": "shared-library",
  "changes": ["src/Models/Donation.cs", "src/Dto/DonationDto.cs"],
  "exposedInterfaces": [
    "Donation.ImpactInvestment: decimal?",
    "DonationDto.ImpactInvestment: decimal?"
  ],
  "buildStatus": "green",
  "notes": "Nullable so every existing row stays valid without a backfill."
}
```

And promote those into `sharedContracts`:

```json
"sharedContracts": {
  "Donation.ImpactInvestment": ["decimal?", "nullable for backward compatibility"],
  "DonationDto.ImpactInvestment": ["decimal?", "maps 1:1, no transform"]
}
```

## Step 4 — Repo 2, `command-api`

On entry, the upstream `sharedContracts` are injected as contracts that **must be
consumed as named.**

This is the rule the whole protocol exists for. If `command-api` decides
`ImpactInvestmentAmount` reads better and renames it locally, then:

- `command-api` compiles ✅
- `query-api` compiles against the shared library's name ✅
- the two do not agree ❌
- and nothing fails until a donation with that field round-trips

Four repositories that each build and do not talk to each other is the characteristic
failure of multi-repo work, and it is always a naming drift, never a logic error.

**If the name is genuinely wrong, change it in `shared-library` and re-advance the band.**
That costs one extra pass and is the only correct move.

## Step 5 — The Mapping Mechanism, Per Repo

The band carries the contract; it does not carry the mapping. Each repository still
identifies its own:

| Repo | Mechanism | The thing that gets forgotten |
|---|---|---|
| `command-api` | AutoMapper profile | A new property needs no config **unless** the profile uses `ForMember` explicitly — then it silently maps to null |
| `query-api` | Dapper read model | The SQL projection is hand-written. A new column is not automatic. |
| `frontend` | Reactive form | The form control, the interface, **and** the template all need it. Two out of three compiles. |

## Step 6 — Advance and Verify

```
python scripts/cross-repo.py band advance
```

Each advance: moves the completed repo out of `remainingRepos`, merges its
`exposedInterfaces` into `sharedContracts`, and writes the checkpoint.

## What Blocks The Band

- A repo whose build is not green does not advance. Downstream work against a broken
  contract is worse than no work.
- A human gate anywhere stops the whole band, not just that repo.
- A lock held by another session means someone else is already in that repo. Wait, do
  not force.

## The Honest Limit

The band tracks contracts and order. It does not verify that a downstream repo *actually
consumed* the contract correctly — that needs an integration test crossing the
repositories, which this system does not run. What it prevents is the drift; what it
cannot prevent is a correct name wired to the wrong thing. Say so when reporting a
completed band.

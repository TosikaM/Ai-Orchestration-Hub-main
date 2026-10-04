---
applyTo: "**/*"
description: How this repository is connected to the AI Orchestrator hub, and which rules win when they disagree.
---

<!-- RENDERED from templates/generic/consumer-instruction.template.md when this repository
     was connected to the hub. The placeholders below are filled by the connector; a value
     the detector could not establish is written as "not detected" rather than guessed,
     because an honest "not found" outranks a plausible guess and a wrong stack sends every
     later suggestion in the wrong direction. -->

# AI Orchestrator — {{REPO_NAME}}

This repository is connected to the **{{ORG}}** orchestrator hub. This file tells an agent
working here what was detected, what capabilities are available, and — most importantly —
which source of truth wins when two of them disagree.

## This repository's profile

| | |
|---|---|
| Repository | `{{REPO_NAME}}` |
| Organization | {{ORG}} |
| Detected stack | {{TECH_STACK}} |
| Architecture | {{ARCHITECTURE}} |
| Framework version | {{FRAMEWORK_VERSION}} |
| Test framework | {{TEST_FRAMEWORK}} |
| Connected on | {{CONNECTION_DATE}} |
| Profile last refreshed | {{LAST_REFRESH}} |

Every row here is a detection result, not a decision. The stack was matched from indicator
files against `config/stack-mappings.json`, which means it identifies what the repository
looks like, not what the team intended. If a row is wrong, correct it in
`.github/orchestrator-context.md` and re-run `/analyze` — do not work around it silently,
because the same wrong value is about to drive the build command, the test command, and
the pattern template that gets loaded.

## Subscribed orchestrator capabilities

{{#SUBSCRIPTIONS}}
- **{{type}}** — `{{remotePath}}` → `{{localPath}}` ({{#required}}required{{/required}}{{^required}}optional{{/required}})
{{/SUBSCRIPTIONS}}

Anything not in that list is not installed here. If a command or agent is missing, the
answer is usually a narrower install profile rather than a bug: re-run the connector with
`-With <component>` to add one component without moving to a wider profile.

## Where the context file lives

`.github/orchestrator-context.md` is this repository's profile — its stack, layer map,
domain entities, integration points, verified commands, and conventions. Read it before
answering any question about this codebase; it is the difference between an answer grounded
in this repository and an answer grounded in a general impression of repositories like it.

`.github/orchestrator-install.json` records what the connector wrote, with a hash per file,
so `doctor` can tell an orchestrator-managed file from one of yours and an uninstall can
remove only what it created.

Two sections of the context file are **never overwritten by a refresh**:

- `## Verified Commands` — a command a human confirmed actually runs here. A one-time
  question whose answer persists beats a permanent "not detected".
- `## Integration Points` — maintained by hand, because a scanner cannot infer them.

Everything else in that file is regenerated, so a hand edit elsewhere in it is lost on the
next refresh. Durable notes belong under `## Orchestrator Notes`.

## Commands available

| Command | What it does |
|---|---|
| `/orchestrator-init` | Connect or re-connect this repository and generate its context |
| `/analyze` · `/explore` | Build or refresh the repo profile; explore a subsystem |
| `/graph` · `/ground` | Structural graph and symbol index; verify claims against the source |
| `/plan` · `/sdlc-start` · `/pipeline` | Plan a change; run the SDLC pipeline; inspect the pipeline graph |
| `/implement` | Implement a change against this repo's conventions |
| `/review` · `/test` · `/qa` · `/verify` | Score a change; generate tests; run the six-phase verification loop |
| `/security` | Security review of the pending change |
| `/adr` · `/document` · `/release` | Record a decision; write docs; prepare a release |
| `/memory` · `/learn` · `/knowledge` | Query and capture durable learnings; ingest reference material |
| `/budget` · `/loop` · `/mcp-compose` | Token accounting; the bounded autonomous loop; multi-tool chains |
| `/repo` · `/mode` · `/doctor` | Switch repositories; switch behavioral mode; diagnose the install |

Commands resolve their build, test, lint and format invocations per stack from the hub's
stack mapping and from `## Verified Commands` in the context file. A phase that could not
run is reported as "not run" — never as passed.

## Convention priority

When two sources disagree, the higher one wins. This order is not a suggestion; it is the
rule an agent applies without asking.

1. **This repository's own `CLAUDE.md` or `.github/copilot-instructions.md`.**
2. **This connector file** — the profile and capabilities above.
3. **Shared best practices** from the hub's memory, which are promoted only after being
   observed in more than one repository.
4. **The stack pattern template** (`templates/{{TECH_STACK}}/`), which is generic advice
   about a technology and knows nothing about this codebase.

The repository always wins. A hub default that overrides a team's stated convention is a
hub that gets uninstalled — and the hub would deserve it, because the team's convention
usually encodes a constraint the hub cannot see, from an integration, an audit requirement,
or a migration still in flight.

Two corollaries worth stating plainly. An existing pattern in this codebase outranks a
"better" pattern from the template even when the template's version is genuinely better;
propose the change, do not perform it as a side effect of unrelated work. And when you set
aside a hub rule because this repository says otherwise, say so in your response and name
the file you followed, so the next reader can tell a deliberate deviation from an accident.

## Auto-update behavior

The repository profile is refreshed when:

- this repository is connected for the first time;
- a change lands on the default branch that touches structure — dependencies, project
  files, or directory layout;
- someone runs `/analyze` (add `--force` to regenerate a profile that is still fresh);
- the profile is more than **14 days** old, which the staleness check reports at session
  start.

Refreshing rewrites the generated sections of `.github/orchestrator-context.md` and leaves
`## Verified Commands`, `## Integration Points`, and `## Orchestrator Notes` untouched.
Skills, agents, prompts and hooks are **not** copied into this repository — they are carried
by the plugin, so upgrading the hub upgrades this repository with no pull request here. The
exception is a deliberately vendored install, where the connector backs up any file it is
about to replace and refuses outright to overwrite a file it did not write.

## Getting help

`/doctor` reports what is installed, what drifted, and what a repair would change before it
changes anything. If a command behaves as though this repository were a different one, the
profile above is the first thing to check.

---

<!-- DO NOT EDIT THIS FILE BY HAND. It is rendered from
     templates/generic/consumer-instruction.template.md in the orchestrator hub, and the
     next connect or refresh will overwrite it, taking your edit with it and leaving no
     record that it existed.

     To change the content for every repository: edit the template in the hub.
     To change something for this repository only: edit .github/orchestrator-context.md,
     or state the convention in this repository's own CLAUDE.md — which, per the priority
     order above, outranks this file anyway. -->

---
name: config-protection
trigger: PreToolUse
matcher: "Edit|Write|MultiEdit"
profiles: [standard, strict]
mode: sync
blocking: true
handler: hooks/runtime/handlers/config-protection.js
description: Denies edits to the files that define this system's quality gates unless an explicit, per-file override is set for the session.
---

# Config Protection — the guard-the-guard hook

This runs before every `Edit`, `Write`, or `MultiEdit` and asks one question: does the
target file define a rule that some other part of the system enforces? If it does, the
edit is denied unless `ORCHESTRATOR_ALLOW_GOVERNANCE_EDIT` names that file for this
session.

## Why this exists

Given a failing gate and the ability to edit the gate, an agent will sometimes edit the
gate. This is not malice; it is an optimizer finding the cheapest path to green, and
changing one number in a JSON file is cheaper than fixing the code that made the number
fail.

That matters more here than in most repositories, because every quality claim this
system makes lives in a file an agent can edit. The discovery and eager token budgets
are numbers in `config/token-budgets.json`. The quality-score floor and the `humanGate`
flags are fields in `config/pipeline-graph.json`. Organization neutrality and structural
validation are checks inside `scripts/validate-structure.py`. The redaction tiers are
patterns in `config/redaction-patterns.json`. Hook registration is
`hooks/hooks.json` and `hooks/runtime/registry.json`. Eval thresholds are in
`evals/evals.json`, and CI enforcement is a workflow file.

"The agent can edit these freely" and "the guarantees hold" cannot both be true. This
hook is what makes the second one true.

## What it checks

Two rules, both intentionally coarse.

**Basenames, not paths.** `isGovernance` compares `path.basename(filePath)` against a
fixed set: the config files above, the validation and measurement scripts, the plugin
and registry manifests, the eval and touchfile manifests, the CI and governance
workflows, and `CODEOWNERS`. A governance file that gets moved is still a governance
file, and a path-based list would silently stop protecting it the day somebody
reorganizes the tree.

**Whole directories.** Anything under `hooks/runtime/`, `.claude-plugin/`, or
`migrations/` is governance whatever it is called. The hook runtime is the thing that
enforces every other gate, so leaving it editable would make the rest of this list
decorative.

The override is read from `ORCHESTRATOR_ALLOW_GOVERNANCE_EDIT`, split on commas or
semicolons. An entry matches by basename or as a path suffix; `*` matches everything.

## Action on a hit

`permissionDecision: deny`, with a reason that names the file, states plainly that
editing it to resolve a failure changes what "passing" means rather than making the work
pass, and gives the three-step path to a legitimate change: say which gate and why it is
wrong here, record the decision with `python scripts/decision.py log`, then re-run with
the override set.

The reason also carries a ratchet note, because one common case is not an evasion at
all: lowering a *measured* budget after a real reduction landed is the ratchet working
as designed. Take the override and record why.

When the override does apply, the hook does not silently step aside. It allows and
attaches a note saying the edit was permitted by the override and that the reason
belongs in the decision log — a permitted governance edit should still be visible in the
transcript.

## Recovery / escape

**Narrow first.** `ORCHESTRATOR_ALLOW_GOVERNANCE_EDIT=<basename>` for one file, for one
session. Deny is not refuse-forever: widening a gate should require a decision, and a
decision should be visible in the shell history of whoever made it. That is a different
thing from being impossible.

**Broader.** Several basenames separated by commas, or `*` for all of them — which is
the point at which you have turned the hook off and should know it.

**Broadest.** `ORCHESTRATOR_DISABLED_HOOKS=pre:edit-write:config-protection`, or
`ORCHESTRATOR_HOOKS_ENABLED=false` for the whole runtime.

## Honest limits

It does not read the diff. It cannot distinguish "lower the quality floor from 80 to 60"
from "fix a typo in a comment" in the same file, so it denies both and makes you say
which one you are doing. That is deliberate, and it is also the source of most of the
friction this hook causes.

Basename matching over-matches. Any file anywhere in the tree named `registry.json` or
`plugin.json` is protected whether or not it governs anything.

The protected set is hand-maintained and will drift. A governance value moved into a
file not on the list is unprotected from the moment it moves, and nothing detects that —
`validate-structure.py` checks hook parity, not whether this list is complete.

It only sees the edit tools. A governance file rewritten through `Bash` — a redirect, a
`sed -i`, a Python one-liner — does not reach this matcher.

And it protects the file, not the intent. An agent that cannot edit the threshold can
still write code that satisfies the threshold without satisfying its purpose. No hook
catches that; review does.

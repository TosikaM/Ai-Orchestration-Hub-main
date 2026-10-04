---
name: token-budget-guard
trigger: SessionStart
matcher: ".*"
profiles: [minimal, standard, strict]
mode: sync
blocking: false
handler: hooks/runtime/handlers/token-budget-guard.js
description: Measures the skill-discovery footprint against the ceiling in config/token-budgets.json and warns at session start when it is over.
---

# Token Budget Guard

This measures the discovery footprint — the `name` and `description` frontmatter of
every skill, which is parsed and held in context in every session before the user types
anything — and compares it against the ceiling in `config/token-budgets.json`. It runs
at session start and, per the registry, is meant to be invoked in-process by
`session-bootstrap` so that session start costs one Node process rather than two.

It replaces a hook the source material specified with `trigger: onSkillLoad`. There is
no such event in any real API. `SessionStart` is the honest equivalent for the cost this
measures, because the discovery footprint is not paid when a skill loads — it is paid
whether or not any skill ever loads.

## Why this exists

Discovery text is the most expensive prose in the system per word, and the least visible.
Nobody sees it. It never appears in a response, it is not part of any file anyone reads
on purpose, and it is loaded in every session in every connected repository. A single
skill whose description grows by two sentences taxes every conversation the organization
has, forever, and the growth is invisible in every review because each individual
addition looks reasonable.

The failure this prevents is therefore not an outage. It is drift: a budget that is
"about right" at the point it was set and forty percent over a year later, with no moment
at which anyone decided to spend the difference.

## What it checks

It walks `<pluginRoot>/skills/*/SKILL.md`, parses the frontmatter with a deliberately
tiny single-line scalar parser — `name` and `description` are single-line by contract,
and pulling in a YAML dependency for two fields would cost more startup than it saves —
and sums `Buffer.byteLength(name + description)` per skill.

Two comparisons follow: the total against `discovery.aggregateFrontmatterBytes`, warning
at `warnAtPercent` (default 85) and reporting OVER above the ceiling, and each skill
against `discovery.perSkillFrontmatterBytes`.

There is a third case, and it is the interesting one. If either ceiling is not a number,
the handler does not skip quietly — it says that the comparison is silently disabled
rather than failing, and points at `validate-structure.py`, whose ratchet pins exist to
catch exactly this. A budget check that no longer checks anything is worse than no budget
check, because it still looks installed.

## Action on a hit

`SessionStart` `additionalContext`. It never blocks: `hardFail` is false by design. A
blown budget degrades answer quality; it is not a safety incident, and halting somebody's
work over it would be a strictly worse outcome than a slightly trimmed prompt.

The warning states the measured bytes against the ceiling, lists each skill over the
per-skill cap with the concrete fix — move trigger, USE FOR, and NOT FOR text into the
skill body's `## Routing` block, where it costs nothing until the skill is actually
loaded — and points at `/budget` for a ranked list of what to cut.

The discovery overrun warns on *every* session start until it is fixed. Unlike the eager
budget, this cost is paid by every conversation in every repository, so the nagging is
proportionate.

## Recovery / escape

**Narrow first, and it is a real fix rather than an escape.** Trim the offending
descriptions. `/budget` ranks them and gives a concrete edit for each.

**If the ceiling is genuinely wrong**, raise it in `config/token-budgets.json` — a
governance edit, so config protection will require `ORCHESTRATOR_ALLOW_GOVERNANCE_EDIT`
and a logged decision. Lowering a measured budget after a real reduction landed is the
ratchet working as designed.

**Broad.** `ORCHESTRATOR_DISABLED_HOOKS=session:start:token-budget-guard`, or
`ORCHESTRATOR_HOOKS_ENABLED=false`.

## Honest limits

It measures bytes, not tokens. Bytes are a stable, cheap proxy that never needs a
tokenizer at session start, and the ratio between the two is not constant across
languages or punctuation. Treat the number as a budget unit, not as a token count.

It measures this plugin's own `skills/` directory and nothing else. Other plugins, the
user's `.claude/skills/`, and everything else in the harness also spend discovery
context, so the real footprint in any given session is larger than the number reported
here — possibly much larger.

It measures the frontmatter that *would* be loaded, not what was. It cannot see which
skills the harness actually offered, nor which ones were invoked.

It says nothing about the eager budget, the context window, or the cost of a turn.
`scripts/context-bill.py` and `/budget` are the tools for those.

And a caveat specific to how it is wired today: `registry.json` records that this handler
is invoked in-process by `session-bootstrap` and `validate-structure.py` exempts it from
the manifest-reachability check on the strength of that note, but
`hooks/runtime/handlers/session-bootstrap.js` does not currently call it. Until it does,
this handler runs only when invoked directly.

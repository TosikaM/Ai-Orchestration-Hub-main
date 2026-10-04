# Shared Memory — Anti-Patterns

<!-- GENERATED from memory/index/entries.json by scripts/memory.py.
     Edit through `python scripts/memory.py`, not by hand: the write path runs
     the redaction and injection guard, and hand edits are lost on the next render. -->

<!-- Everything below the banner is ship-time scaffolding. `scripts/memory.py` rewrites
     this file from the index on the next write, and this orientation prose does not
     survive that render. The durable explanation lives in `memory/README.md`, which is
     hand-maintained and is not rendered from anything. -->

## How this works

An anti-pattern entry records something that was tried, failed, and is worth not trying
again. Entries arrive scoped to a single repository at confidence `0.4` and reach this
file only by promotion — confidence ≥ 0.7 **and** observed in ≥ 2 repositories. Anything
listed here therefore claims to be wrong in more than one place, which is the only claim
that justifies loading it in every repository.

Capture one with:

```
python scripts/memory.py capture --type anti-pattern \
  --title "..." --context "..." --resolution "..." [--applies-to <stack>]
```

Write the `--resolution` as what to do *instead*. An anti-pattern with no alternative
tells an agent to stop without telling it where to go, and the usual outcome is that it
does the same thing with different names. Write the `--context` as the circumstances in
which the failure appeared; it is excluded from duplicate detection precisely because it
is repo-specific, so it costs nothing to make it concrete.

<!-- ENTRY FORMAT — rendered, not authored. Each promoted entry appears as:

### <title>
- **Confidence**: <effective, after decay> (recorded <stored value>)
- **Seen in**: <repo>, <repo>
- **Context**: <where and when the failure showed up>
- **Resolution**: <what to do instead>
- **Applies to**: <stack or "all">
- **First observed**: <ISO-8601> · **Last reinforced**: <ISO-8601>
- **Counter-examples**: <count, only when one has been recorded>
- **Related**: <title of a weakly-matching entry, when one exists>

Entries are ordered by effective confidence, highest first.
-->

_No entries yet. Memory ships empty — seeding it with invented learnings would poison
the well on day one._

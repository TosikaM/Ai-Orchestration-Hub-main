# Shared Memory — Best Practices

<!-- GENERATED from memory/index/entries.json by scripts/memory.py.
     Edit through `python scripts/memory.py`, not by hand: the write path runs
     the redaction and injection guard, and hand edits are lost on the next render. -->

<!-- Everything below the banner is ship-time scaffolding. `scripts/memory.py` rewrites
     this file from the index on the next write, and this orientation prose does not
     survive that render. The durable explanation lives in `memory/README.md`, which is
     hand-maintained and is not rendered from anything. -->

## How this works

A best-practice entry records an approach that worked, together with the reason it
worked. Like every shared entry it arrives repo-scoped at confidence `0.4` and reaches
this file only by promotion — confidence ≥ 0.7 **and** observed in ≥ 2 repositories.

Capture one with:

```
python scripts/memory.py capture --type best-practice \
  --title "..." --context "..." --resolution "..." [--applies-to <stack>]
```

The bar for this category is higher than it looks, and it is worth being deliberate about
why. "It worked" is not evidence that the approach caused the outcome, and a practice
promoted on a single satisfying session becomes advice injected into every repository
that connects to this hub. Prefer entries that name the failure the practice avoids: a
practice whose justification is a concrete avoided failure survives contact with a
different codebase, and a practice whose justification is that it felt clean does not.

Set `--applies-to` to the narrowest stack the claim is actually true for. A
recommendation labeled `all` when it is really about one framework is the most common way
this file degrades — it stays technically defensible while being useless in most of the
places it loads.

<!-- ENTRY FORMAT — rendered, not authored. Each promoted entry appears as:

### <title>
- **Confidence**: <effective, after decay> (recorded <stored value>)
- **Seen in**: <repo>, <repo>
- **Context**: <the situation the practice applies to>
- **Resolution**: <the practice, and the failure it avoids>
- **Applies to**: <stack or "all">
- **First observed**: <ISO-8601> · **Last reinforced**: <ISO-8601>
- **Counter-examples**: <count, only when one has been recorded>
- **Related**: <title of a weakly-matching entry, when one exists>

Entries are ordered by effective confidence, highest first.
-->

_No entries yet. Memory ships empty — seeding it with invented learnings would poison
the well on day one._
